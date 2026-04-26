"""
ClawVault - Fact Extractor (Memória Ativa)
===========================================

Após cada conversa, roda em background um modelo BARATO pra extrair
fatos estruturados, decisões, aprendizados e ações pendentes.

CORREÇÕES vs P1 original:
  - _is_duplicate() usa batch embedding ao invés de N chamadas individuais
  - ensure_facts_schema() chamado no __init__ — garantido ANTES de qualquer query
  - Logging estruturado (print → journalctl)
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.core.config import VAULT_DIR, TaskComplexity
from backend.core.database import db
from backend.memory.vault import vault, VaultNote


# ==========================================================================
# SCHEMA DO BANCO (extensão)
# ==========================================================================

SCHEMA_FACTS = """
-- Fatos estruturados extraídos automaticamente das conversas
CREATE TABLE IF NOT EXISTS facts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    type            TEXT NOT NULL,        -- fact, decision, learning, todo
    content         TEXT NOT NULL,
    entity          TEXT,                 -- entidade principal (projeto, pessoa)
    entities_json   TEXT,                 -- JSON array de todas entidades
    confidence      REAL DEFAULT 0.7,     -- 0.0-1.0
    source_conv     INTEGER,              -- conversation_id de origem
    source_msg      INTEGER,              -- message_id de origem
    deprecated      INTEGER DEFAULT 0,    -- 1 se foi substituído/anulado
    deprecated_by   INTEGER,              -- ID do fato que substituiu
    confirmed_count INTEGER DEFAULT 1,    -- vezes que foi confirmado
    last_confirmed  TIMESTAMP,
    vault_path      TEXT,                 -- path do .md gerado no vault
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata_json   TEXT
);

CREATE INDEX IF NOT EXISTS idx_facts_entity ON facts(entity);
CREATE INDEX IF NOT EXISTS idx_facts_type   ON facts(type);
CREATE INDEX IF NOT EXISTS idx_facts_active ON facts(deprecated, type);
"""


def ensure_facts_schema():
    """Garante que tabela facts existe. Chamada no __init__ do extractor."""
    with db.connect() as conn:
        conn.executescript(SCHEMA_FACTS)
        conn.commit()


# ==========================================================================
# DATA CLASS
# ==========================================================================

@dataclass
class Fact:
    type: str
    content: str
    entity: Optional[str] = None
    entities: list[str] = field(default_factory=list)
    confidence: float = 0.7
    source_conv: Optional[int] = None
    source_msg: Optional[int] = None

    def to_markdown(self) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        ents = ", ".join([f'"{e}"' for e in self.entities]) if self.entities else ""
        return f"""---
type: {self.type}
entity: {self.entity or ''}
entities: [{ents}]
confidence: {self.confidence}
source_conversation: {self.source_conv or ''}
created: {ts}
---

# {self.type.upper()}: {self.content[:80]}

{self.content}
"""


# ==========================================================================
# PROMPT DE EXTRAÇÃO
# ==========================================================================

EXTRACTION_PROMPT = """Você é um extrator de fatos. Sua tarefa: ler a conversa abaixo e extrair informações ESTRUTURADAS.

Tipos de extração:
- **fact**: afirmação sobre o usuário, seus projetos, sua infraestrutura ou contexto
- **decision**: decisão técnica ou de negócio tomada na conversa
- **learning**: lição aprendida (algo que funcionou ou que NÃO funcionou)
- **todo**: ação pendente que ficou em aberto

REGRAS:
1. Só extraia o que aparece EXPLICITAMENTE na conversa. Não infira.
2. Cada item deve ser uma frase CURTA (máx 200 chars).
3. Identifique a entidade principal (nome de projeto, pessoa, sistema). Se não houver, deixe null.
4. Confidence 0.9 = absolutamente claro; 0.5 = inferência razoável; <0.5 = não extraia.
5. Se a conversa não tem nada extraível, retorne array vazio [].

CONVERSA:
{conversation}

RESPONDA EM JSON VÁLIDO no formato:
[
  {{"type": "fact", "content": "...", "entity": "...", "entities": [...], "confidence": 0.9}},
  {{"type": "decision", "content": "...", "entity": "...", "entities": [...], "confidence": 0.85}}
]

JSON:"""


# ==========================================================================
# EXTRAÇÃO PRINCIPAL
# ==========================================================================

class FactExtractor:
    """Extrai fatos estruturados de conversas."""

    def __init__(self):
        ensure_facts_schema()
        print(f"[fact_extractor] Schema OK — tabela facts pronta")

    def extract_from_conversation(self, conversation_id: int) -> dict:
        start = time.time()
        print(f"[fact_extractor] Iniciando extração conv={conversation_id}")

        msgs = db.fetch_all(
            """
            SELECT id, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            """,
            (conversation_id,),
        )

        if len(msgs) < 2:
            print(f"[fact_extractor] conv={conversation_id} — conversa muito curta ({len(msgs)} msgs)")
            return {"extracted": 0, "saved": 0, "skipped": 0, "errors": 0,
                    "reason": "conversa muito curta"}

        conv_text = "\n\n".join(
            f"**{m['role'].upper()}:** {m['content']}" for m in msgs
        )

        MAX_CHARS = 8000
        if len(conv_text) > MAX_CHARS:
            conv_text = conv_text[-MAX_CHARS:]

        from backend.llm.router import router, LLMRequest

        try:
            response = router.route(LLMRequest(
                prompt=EXTRACTION_PROMPT.format(conversation=conv_text),
                complexity_hint=TaskComplexity.SIMPLE,
                temperature=0.1,
                max_tokens=1500,
            ))
        except Exception as e:
            print(f"[fact_extractor] ERROR LLM call conv={conversation_id}: {e}")
            return {"extracted": 0, "saved": 0, "skipped": 0, "errors": 1,
                    "reason": f"LLM call failed: {e}"}

        if response.error or not response.content:
            print(f"[fact_extractor] ERROR response conv={conversation_id}: {response.error or 'empty'}")
            return {"extracted": 0, "saved": 0, "skipped": 0, "errors": 1,
                    "reason": response.error or "empty response"}

        items = self._parse_json_response(response.content)

        if not items:
            elapsed = time.time() - start
            print(f"[fact_extractor] conv={conversation_id} — nada extraído ({elapsed:.1f}s)")
            return {"extracted": 0, "saved": 0, "skipped": 0, "errors": 0,
                    "reason": "nada extraído (conversa sem fatos novos)"}

        saved = 0
        skipped = 0
        errors = 0

        for item in items:
            try:
                if not self._validate_item(item):
                    skipped += 1
                    continue

                fact = Fact(
                    type=item["type"],
                    content=item["content"],
                    entity=item.get("entity") or None,
                    entities=item.get("entities") or [],
                    confidence=float(item.get("confidence", 0.7)),
                    source_conv=conversation_id,
                )

                if self._is_duplicate(fact):
                    self._increment_confirmation(fact)
                    skipped += 1
                    continue

                self._save_fact(fact)
                saved += 1

            except Exception as e:
                print(f"[fact_extractor] ERROR processando item: {e}")
                errors += 1
                continue

        elapsed = time.time() - start
        print(f"[fact_extractor] conv={conversation_id} — {saved} salvos, {skipped} skip, {errors} err ({elapsed:.1f}s)")
        return {
            "extracted": len(items),
            "saved": saved,
            "skipped_duplicate": skipped,
            "errors": errors,
        }

    def _parse_json_response(self, text: str) -> list[dict]:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    def _validate_item(self, item: dict) -> bool:
        if not isinstance(item, dict):
            return False
        if item.get("type") not in ("fact", "decision", "learning", "todo"):
            return False
        content = item.get("content", "").strip()
        if not content or len(content) < 10 or len(content) > 500:
            return False
        try:
            conf = float(item.get("confidence", 0.7))
            if conf < 0.5:
                return False
        except (ValueError, TypeError):
            return False
        return True

    def _is_duplicate(self, fact: Fact) -> bool:
        """
        CORREÇÃO: usa batch embedding ao invés de N chamadas individuais.
        """
        # Match exato
        existing = db.fetch_one(
            """
            SELECT id FROM facts
            WHERE type = ? AND content = ? AND deprecated = 0
            LIMIT 1
            """,
            (fact.type, fact.content),
        )
        if existing:
            return True

        # Batch embedding para deduplicação semântica
        try:
            from backend.embeddings import embed_batch, similarity
            similar_candidates = db.fetch_all(
                """
                SELECT id, content FROM facts
                WHERE type = ? AND deprecated = 0
                  AND (entity = ? OR entity IS NULL)
                LIMIT 50
                """,
                (fact.type, fact.entity),
            )
            if not similar_candidates:
                return False

            # Batch embed: novo fato + todos candidatos de uma vez
            all_texts = [fact.content] + [c["content"] for c in similar_candidates]
            all_vecs = embed_batch(all_texts)
            new_vec = all_vecs[0]

            for i, c in enumerate(similar_candidates):
                if similarity(new_vec, all_vecs[i + 1]) > 0.88:
                    return True
        except ImportError:
            pass

        return False

    def _increment_confirmation(self, fact: Fact) -> None:
        db.execute(
            """
            UPDATE facts
            SET confirmed_count = confirmed_count + 1,
                last_confirmed = CURRENT_TIMESTAMP
            WHERE type = ? AND content = ? AND deprecated = 0
            """,
            (fact.type, fact.content),
        )

    def _save_fact(self, fact: Fact) -> int:
        cursor = db.execute(
            """
            INSERT INTO facts
              (type, content, entity, entities_json, confidence,
               source_conv, last_confirmed)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (fact.type, fact.content, fact.entity,
             json.dumps(fact.entities, ensure_ascii=False),
             fact.confidence, fact.source_conv),
        )
        fact_id = cursor.lastrowid

        try:
            note_title = f"{fact.type}_{fact_id}_{(fact.entity or 'geral')[:30]}"
            note = VaultNote(
                title=note_title,
                content=fact.to_markdown(),
                layer="wiki",
                tags=[fact.type, fact.entity] if fact.entity else [fact.type],
                entities=fact.entities,
            )
            filepath = vault.save_note(note, subfolder="fatos")
            rel_path = str(filepath.relative_to(VAULT_DIR))

            db.execute(
                "UPDATE facts SET vault_path = ? WHERE id = ?",
                (rel_path, fact_id),
            )

            try:
                from backend.search import index_note
                index_note(filepath)
            except ImportError:
                pass
        except Exception:
            pass

        return fact_id


# ==========================================================================
# RECUPERAÇÃO DE FATOS (pra injetar em prompts)
# ==========================================================================

def get_facts_for_context(
    query: Optional[str] = None,
    entity: Optional[str] = None,
    types: Optional[list[str]] = None,
    limit: int = 10,
) -> list[dict]:
    where_clauses = ["deprecated = 0"]
    params = []

    if types:
        placeholders = ",".join("?" * len(types))
        where_clauses.append(f"type IN ({placeholders})")
        params.extend(types)

    if entity:
        where_clauses.append("(entity = ? OR entities_json LIKE ?)")
        params.extend([entity, f'%"{entity}"%'])

    where_sql = " AND ".join(where_clauses)

    rows = db.fetch_all(
        f"""
        SELECT id, type, content, entity, confidence, confirmed_count, created_at
        FROM facts
        WHERE {where_sql}
        ORDER BY confirmed_count DESC, created_at DESC
        LIMIT ?
        """,
        tuple(params) + (limit,),
    )

    return rows


def format_facts_for_prompt(facts: list[dict]) -> str:
    if not facts:
        return ""

    by_type = {"fact": [], "decision": [], "learning": [], "todo": []}
    for f in facts:
        t = f.get("type", "fact")
        if t in by_type:
            by_type[t].append(f["content"])

    sections = []
    if by_type["fact"]:
        sections.append("**FATOS CONHECIDOS:**\n" + "\n".join(f"- {x}" for x in by_type["fact"]))
    if by_type["decision"]:
        sections.append("**DECISÕES TOMADAS:**\n" + "\n".join(f"- {x}" for x in by_type["decision"]))
    if by_type["learning"]:
        sections.append("**LIÇÕES APRENDIDAS:**\n" + "\n".join(f"- {x}" for x in by_type["learning"]))
    if by_type["todo"]:
        sections.append("**AÇÕES PENDENTES:**\n" + "\n".join(f"- {x}" for x in by_type["todo"]))

    return "\n\n".join(sections)


# ==========================================================================
# DEPRECATION
# ==========================================================================

def deprecate_fact(fact_id: int, replaced_by: Optional[int] = None) -> bool:
    cursor = db.execute(
        """
        UPDATE facts
        SET deprecated = 1, deprecated_by = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (replaced_by, fact_id),
    )
    return cursor.rowcount > 0


def deprecate_facts_about(entity: str) -> int:
    cursor = db.execute(
        """
        UPDATE facts
        SET deprecated = 1, updated_at = CURRENT_TIMESTAMP
        WHERE deprecated = 0 AND (
              entity = ?
           OR entities_json LIKE ?
        )
        """,
        (entity, f'%"{entity}"%'),
    )
    return cursor.rowcount


# ==========================================================================
# STATS
# ==========================================================================

def stats() -> dict:
    by_type = db.fetch_all(
        """
        SELECT type, COUNT(*) AS n
        FROM facts WHERE deprecated = 0
        GROUP BY type
        """
    )
    deprecated = db.fetch_one(
        "SELECT COUNT(*) AS n FROM facts WHERE deprecated = 1"
    )
    recent = db.fetch_one(
        """
        SELECT COUNT(*) AS n FROM facts
        WHERE deprecated = 0 AND created_at >= datetime('now', '-7 days')
        """
    )
    return {
        "by_type":         {r["type"]: r["n"] for r in by_type},
        "total_active":    sum(r["n"] for r in by_type),
        "total_deprecated": deprecated["n"] if deprecated else 0,
        "added_last_7d":   recent["n"] if recent else 0,
    }


# Instância global
extractor = FactExtractor()
