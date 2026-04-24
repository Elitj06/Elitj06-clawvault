"""
ClawVault - Sistema de Memória Hierárquica
============================================

Organiza a memória em 4 camadas otimizadas para economia de tokens:

┌─────────────────────────────────────────────────────────────────┐
│ QUENTE (RAM)    │ Últimas 20 mensagens da conversa atual        │
│                 │ Acesso: instantâneo │ Custo: zero             │
├─────────────────────────────────────────────────────────────────┤
│ MORNA (SQLite)  │ Últimos 7 dias, busca por palavra-chave       │
│                 │ Acesso: milissegundos │ Custo: zero           │
├─────────────────────────────────────────────────────────────────┤
│ FRIA (Vault)    │ 7-90 dias, busca semântica por embeddings     │
│                 │ Acesso: centenas de ms │ Custo: micro         │
├─────────────────────────────────────────────────────────────────┤
│ ARQUIVO (gzip)  │ +90 dias, só recupera se explicitamente pedir │
│                 │ Acesso: segundos │ Custo: zero                │
└─────────────────────────────────────────────────────────────────┘

O sistema sumariza automaticamente conversas que crescem muito,
mantendo apenas o essencial no contexto enviado ao LLM.
"""

import gzip
import hashlib
import json
import uuid
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from backend.core.config import MEMORY_CONFIG, VAULT_DIR
from backend.core.database import db


# ==========================================================================
# ESTRUTURAS
# ==========================================================================

@dataclass
class MemoryEntry:
    """Representa uma entrada de memória."""
    role: str           # user, assistant, system
    content: str
    timestamp: str      # ISO format
    tokens: int = 0
    conversation_id: Optional[int] = None
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        return cls(**data)


# ==========================================================================
# CAMADA QUENTE (em RAM)
# ==========================================================================

class HotMemory:
    """
    Memória imediata — as últimas N mensagens da conversa ativa.
    Tudo em RAM, acesso instantâneo, zero custo.
    """

    def __init__(self):
        self._conversations: dict[int, deque[MemoryEntry]] = {}
        self.max_messages = MEMORY_CONFIG.hot_max_messages
        self.max_tokens = MEMORY_CONFIG.hot_max_tokens

    def add(self, conversation_id: int, entry: MemoryEntry) -> None:
        """Adiciona entrada à memória quente da conversa."""
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = deque(maxlen=self.max_messages)
        self._conversations[conversation_id].append(entry)

    def get(self, conversation_id: int) -> list[MemoryEntry]:
        """Retorna as mensagens quentes de uma conversa."""
        if conversation_id not in self._conversations:
            return []
        return list(self._conversations[conversation_id])

    def get_within_budget(
        self, conversation_id: int, token_budget: int
    ) -> list[MemoryEntry]:
        """Retorna apenas as mensagens que cabem no budget de tokens."""
        entries = self.get(conversation_id)
        # Começa das mais recentes e volta até esgotar budget
        selected = []
        total = 0
        for entry in reversed(entries):
            if total + entry.tokens > token_budget:
                break
            selected.insert(0, entry)
            total += entry.tokens
        return selected

    def clear(self, conversation_id: int) -> None:
        """Limpa memória quente de uma conversa."""
        self._conversations.pop(conversation_id, None)


# ==========================================================================
# CAMADA MORNA (SQLite)
# ==========================================================================

class WarmMemory:
    """
    Memória morna — últimos N dias, armazenada em SQLite.
    Busca por palavra-chave (LIKE) ou por data. Sem custo de API.
    """

    def store_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        model_used: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        metadata: Optional[dict] = None,
    ) -> int:
        """Salva mensagem na camada morna."""
        cursor = db.execute(
            """
            INSERT INTO messages
            (conversation_id, role, content, model_used,
             input_tokens, output_tokens, cost_usd, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id, role, content, model_used,
                input_tokens, output_tokens, cost_usd,
                json.dumps(metadata) if metadata else None,
            ),
        )
        return cursor.lastrowid

    def search_by_keyword(
        self,
        keyword: str,
        conversation_id: Optional[int] = None,
        days: int = 7,
        limit: int = 10,
    ) -> list[dict]:
        """Busca mensagens contendo palavra-chave."""
        since = datetime.now() - timedelta(days=days)
        if conversation_id:
            sql = """
                SELECT * FROM messages
                WHERE content LIKE ? AND conversation_id = ?
                  AND created_at >= ?
                ORDER BY created_at DESC LIMIT ?
            """
            params = (f"%{keyword}%", conversation_id, since, limit)
        else:
            sql = """
                SELECT * FROM messages
                WHERE content LIKE ? AND created_at >= ?
                ORDER BY created_at DESC LIMIT ?
            """
            params = (f"%{keyword}%", since, limit)
        return db.fetch_all(sql, params)

    def get_recent(
        self, conversation_id: int, limit: int = 50
    ) -> list[dict]:
        """Pega as N mensagens mais recentes de uma conversa."""
        return db.fetch_all(
            """
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (conversation_id, limit),
        )


# ==========================================================================
# CAMADA FRIA (Vault + Embeddings)
# ==========================================================================

class ColdMemory:
    """
    Memória fria — vault markdown com busca semântica via embeddings.

    Notas ficam como arquivos .md em vault/, facilitando leitura humana.
    Embeddings são guardados no SQLite para busca por similaridade.
    """

    def __init__(self, vault_path: Path = VAULT_DIR):
        self.vault_path = vault_path
        self.vault_path.mkdir(parents=True, exist_ok=True)

        # Subpastas organizacionais
        (self.vault_path / "conversas").mkdir(exist_ok=True)
        (self.vault_path / "notas").mkdir(exist_ok=True)
        (self.vault_path / "projetos").mkdir(exist_ok=True)
        (self.vault_path / "resumos").mkdir(exist_ok=True)

    def save_note(
        self,
        content: str,
        title: str,
        folder: str = "notas",
        tags: Optional[list[str]] = None,
    ) -> Path:
        """Salva uma nota no vault."""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)
        filename = f"{timestamp}_{safe_title}.md"
        filepath = self.vault_path / folder / filename

        frontmatter = [
            "---",
            f"title: {title}",
            f"date: {timestamp}",
            f"tags: {tags or []}",
            "---",
            "",
            content,
        ]
        filepath.write_text("\n".join(frontmatter), encoding="utf-8")
        return filepath

    def save_conversation_summary(
        self,
        conversation_id: int,
        summary: str,
        title: str,
        key_points: Optional[list[str]] = None,
    ) -> Path:
        """Salva resumo de uma conversa no vault."""
        # Salva no vault como arquivo legível
        content = f"# {title}\n\n## Resumo\n\n{summary}\n"
        if key_points:
            content += "\n## Pontos-chave\n\n"
            content += "\n".join(f"- {p}" for p in key_points)

        filepath = self.save_note(content, title, folder="resumos", tags=["conversa"])

        # Também salva no banco
        db.execute(
            """
            INSERT OR REPLACE INTO conversation_summaries
            (conversation_id, summary, key_points)
            VALUES (?, ?, ?)
            """,
            (conversation_id, summary, json.dumps(key_points or [])),
        )
        return filepath

    def search_notes_text(self, query: str, limit: int = 5) -> list[dict]:
        """
        Busca simples por texto nos arquivos do vault.
        (Busca semântica real requer embeddings — vem depois)
        """
        results = []
        query_lower = query.lower()

        for md_file in self.vault_path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    # Extrai snippet em volta da palavra-chave
                    idx = content.lower().find(query_lower)
                    start = max(0, idx - 100)
                    end = min(len(content), idx + 200)
                    snippet = content[start:end]

                    results.append({
                        "path": str(md_file.relative_to(self.vault_path)),
                        "snippet": snippet,
                        "full_path": str(md_file),
                    })
                    if len(results) >= limit:
                        break
            except Exception:
                continue

        return results

    def read_note(self, relative_path: str) -> Optional[str]:
        """Lê conteúdo de uma nota pelo caminho relativo."""
        filepath = self.vault_path / relative_path
        if filepath.exists() and filepath.is_file():
            return filepath.read_text(encoding="utf-8")
        return None


# ==========================================================================
# CAMADA ARQUIVO (comprimido)
# ==========================================================================

class ArchiveMemory:
    """
    Memória arquivo — conversas antigas comprimidas, raramente acessadas.
    Fica em vault/arquivo/ como .md.gz para economizar espaço.
    """

    def __init__(self, vault_path: Path = VAULT_DIR):
        self.archive_path = vault_path / "arquivo"
        self.archive_path.mkdir(parents=True, exist_ok=True)

    def archive_conversation(self, conversation_id: int) -> Optional[Path]:
        """Arquiva uma conversa antiga."""
        conv = db.fetch_one(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        if not conv:
            return None

        messages = db.fetch_all(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
            (conversation_id,),
        )

        # Monta markdown da conversa inteira
        content = [
            f"# {conv.get('title', 'Conversa sem título')}",
            f"\n*Criada em: {conv['created_at']}*",
            f"*ID: {conv['uuid']}*\n",
        ]
        for msg in messages:
            content.append(f"\n## {msg['role'].upper()}\n")
            content.append(msg['content'])

        full_text = "\n".join(content).encode("utf-8")

        # Comprime e salva
        filename = f"{conv['uuid']}.md.gz"
        filepath = self.archive_path / filename
        with gzip.open(filepath, "wb") as f:
            f.write(full_text)

        # Marca como arquivada no banco
        db.execute(
            "UPDATE conversations SET archived = 1 WHERE id = ?",
            (conversation_id,),
        )

        return filepath

    def restore_conversation(self, uuid_str: str) -> Optional[str]:
        """Restaura uma conversa arquivada."""
        filepath = self.archive_path / f"{uuid_str}.md.gz"
        if not filepath.exists():
            return None
        with gzip.open(filepath, "rb") as f:
            return f.read().decode("utf-8")


# ==========================================================================
# ORQUESTRADOR DE MEMÓRIA
# ==========================================================================

class MemoryManager:
    """
    Orquestrador que une as 4 camadas de memória.
    É a interface principal que o resto do sistema usa.
    """

    def __init__(self):
        self.hot = HotMemory()
        self.warm = WarmMemory()
        self.cold = ColdMemory()
        self.archive = ArchiveMemory()

    def create_conversation(
        self, title: Optional[str] = None, agent_name: str = "default"
    ) -> int:
        """Cria uma nova conversa e retorna seu ID."""
        conv_uuid = str(uuid.uuid4())
        cursor = db.execute(
            """
            INSERT INTO conversations (uuid, title, agent_name)
            VALUES (?, ?, ?)
            """,
            (conv_uuid, title or f"Conversa {conv_uuid[:8]}", agent_name),
        )
        return cursor.lastrowid

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        model_used: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> int:
        """Adiciona mensagem (salva morna + atualiza quente)."""
        # Salva no banco (camada morna)
        msg_id = self.warm.store_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

        # Adiciona à memória quente (RAM)
        entry = MemoryEntry(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            tokens=input_tokens + output_tokens,
            conversation_id=conversation_id,
        )
        self.hot.add(conversation_id, entry)

        return msg_id

    def get_context_for_llm(
        self, conversation_id: int, token_budget: int = 4000
    ) -> list[dict]:
        """
        Monta o contexto a ser enviado para o LLM, respeitando budget.
        Prioriza memória quente (RAM) e preenche com morna se necessário.
        """
        hot_entries = self.hot.get_within_budget(conversation_id, token_budget)

        # Se a memória quente está vazia (ex: reinício), carrega da morna
        if not hot_entries:
            warm_msgs = self.warm.get_recent(conversation_id, limit=20)
            return [
                {"role": m["role"], "content": m["content"]}
                for m in reversed(warm_msgs)
            ]

        return [{"role": e.role, "content": e.content} for e in hot_entries]

    def search(
        self, query: str, conversation_id: Optional[int] = None
    ) -> dict:
        """
        Busca em todas as camadas e retorna resultados unificados.
        """
        return {
            "warm": self.warm.search_by_keyword(query, conversation_id, limit=5),
            "cold": self.cold.search_notes_text(query, limit=5),
        }


# Instância global
memory = MemoryManager()
