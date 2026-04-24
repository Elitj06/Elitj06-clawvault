"""
ClawVault - Sistema de Memória Multi-Agente
=============================================

Implementa três conceitos que trabalham juntos:

1. SHARED MEMORY BUS
   Canal que o agente principal usa para passar "pacotes de memória"
   para sub-agentes, ou entre sub-agentes. Cada pacote é namespaced
   (escopo limitado) para não poluir o contexto do destino.

2. PROGRESSIVE AGENT MEMORY
   Cada agente tem 3 níveis de memória própria:
   - CORE: fatos fundamentais (sempre vão no contexto, <500 tokens)
   - LEARNED: padrões aprendidos (incluídos por relevância)
   - EPISODIC: experiências recentes (últimas N interações)

   A memória cresce de forma OTIMIZADA: a cada N interações o
   agente destila experiências em padrões, e padrões antigos que
   não foram usados viram arquivo (não vão mais pro contexto).

3. LEARNING LOOP (inspirado no Hermes)
   Após cada tarefa bem-sucedida:
   - Extract: o que foi aprendido?
   - Evaluate: isso é genérico ou específico?
   - Store: vai pra CORE, LEARNED ou EPISODIC?
   - Compress: se LEARNED crescer demais, sumariza

ECONOMIA: cada agente só carrega SUA memória + memórias compartilhadas
RELEVANTES. Nunca carrega o vault inteiro.
"""

import json
import hashlib
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

from backend.core.config import VAULT_DIR
from backend.core.database import db
from backend.memory.vault import Vault, VaultNote


# ==========================================================================
# ESQUEMA DO BANCO (tabelas específicas da multi-memory)
# ==========================================================================

SCHEMA_MULTI_AGENT = """
-- Cada agente tem um registro aqui
CREATE TABLE IF NOT EXISTS agents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT UNIQUE NOT NULL,
    role            TEXT,
    parent_agent    TEXT,                -- agente que criou este (se sub-agente)
    is_main         INTEGER DEFAULT 0,   -- é o agente principal?
    system_prompt   TEXT,
    preferred_model TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_calls     INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0
);

-- Memória de cada agente (3 níveis)
CREATE TABLE IF NOT EXISTS agent_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name      TEXT NOT NULL,
    level           TEXT NOT NULL,        -- 'core', 'learned', 'episodic'
    key             TEXT NOT NULL,        -- identificador curto
    content         TEXT NOT NULL,        -- o conteúdo da memória
    context         TEXT,                 -- em que situação foi criada
    relevance       INTEGER DEFAULT 5,    -- 1-10
    usage_count     INTEGER DEFAULT 0,    -- quantas vezes foi usada
    last_used_at    TIMESTAMP,
    tokens          INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    compressed_from TEXT,                 -- se veio de sumarização, IDs origem
    UNIQUE(agent_name, level, key)
);

CREATE INDEX IF NOT EXISTS idx_agent_mem_agent ON agent_memory(agent_name, level);
CREATE INDEX IF NOT EXISTS idx_agent_mem_relevance ON agent_memory(relevance DESC);

-- Memória compartilhada (canal entre agentes)
CREATE TABLE IF NOT EXISTS shared_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    namespace       TEXT NOT NULL,        -- escopo (ex: 'project:gymflow')
    key             TEXT NOT NULL,
    content         TEXT NOT NULL,
    source_agent    TEXT,                 -- quem criou
    target_agents   TEXT,                 -- JSON array: quem pode ler (null=todos)
    expires_at      TIMESTAMP,            -- null = permanente
    tokens          INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(namespace, key)
);

CREATE INDEX IF NOT EXISTS idx_shared_ns ON shared_memory(namespace);

-- Log de aprendizado (learning loop)
CREATE TABLE IF NOT EXISTS learning_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name      TEXT NOT NULL,
    task_summary    TEXT,
    extracted       TEXT,                 -- o que foi aprendido
    stored_as       TEXT,                 -- core/learned/episodic
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def ensure_multi_agent_schema():
    """Aplica o schema multi-agente no banco."""
    with db.connect() as conn:
        conn.executescript(SCHEMA_MULTI_AGENT)
        conn.commit()


# ==========================================================================
# ESTRUTURAS
# ==========================================================================

class MemoryLevel:
    """Níveis de memória de um agente."""
    CORE = "core"           # sempre vai no contexto
    LEARNED = "learned"     # vai quando relevante
    EPISODIC = "episodic"   # últimas N experiências


@dataclass
class AgentMemoryEntry:
    """Uma entrada de memória de um agente."""
    level: str
    key: str
    content: str
    context: Optional[str] = None
    relevance: int = 5
    usage_count: int = 0
    tokens: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SharedMemoryPacket:
    """Pacote de memória passado entre agentes."""
    namespace: str        # ex: 'project:gymflow', 'task:pitch-review'
    key: str
    content: str
    source_agent: Optional[str] = None
    target_agents: Optional[list[str]] = None  # None = todos
    expires_at: Optional[str] = None


# ==========================================================================
# AGENT REGISTRY
# ==========================================================================

class AgentRegistry:
    """Cadastro de agentes no sistema."""

    @staticmethod
    def register(
        name: str,
        role: str = "",
        parent_agent: Optional[str] = None,
        is_main: bool = False,
        system_prompt: Optional[str] = None,
        preferred_model: Optional[str] = None,
    ) -> int:
        """Registra um novo agente. Retorna ID."""
        ensure_multi_agent_schema()

        cursor = db.execute(
            """
            INSERT INTO agents (name, role, parent_agent, is_main,
                               system_prompt, preferred_model)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                role = excluded.role,
                parent_agent = excluded.parent_agent,
                system_prompt = excluded.system_prompt,
                preferred_model = excluded.preferred_model,
                last_active = CURRENT_TIMESTAMP
            """,
            (name, role, parent_agent, int(is_main), system_prompt, preferred_model),
        )
        return cursor.lastrowid

    @staticmethod
    def get(name: str) -> Optional[dict]:
        return db.fetch_one("SELECT * FROM agents WHERE name = ?", (name,))

    @staticmethod
    def list_all() -> list[dict]:
        return db.fetch_all("SELECT * FROM agents ORDER BY is_main DESC, name")

    @staticmethod
    def list_subagents(parent: str) -> list[dict]:
        return db.fetch_all(
            "SELECT * FROM agents WHERE parent_agent = ?", (parent,)
        )


# ==========================================================================
# PROGRESSIVE AGENT MEMORY
# ==========================================================================

class ProgressiveAgentMemory:
    """
    Memória individual de um agente — cresce de forma otimizada.

    Como funciona:
    - CORE (~500 tokens): fatos imutáveis, sempre vão no contexto
    - LEARNED (~2000 tokens): padrões aprendidos, vão por relevância
    - EPISODIC (ilimitado): últimas 50 experiências, antigas são compactadas

    A CADA 10 interações, o método consolidate() destila experiências
    episódicas em padrões LEARNED. Assim a memória melhora sem inchar.
    """

    # Limites por nível (em tokens aproximados)
    CORE_MAX_TOKENS = 500
    LEARNED_MAX_TOKENS = 2000
    EPISODIC_MAX_COUNT = 50
    CONSOLIDATION_THRESHOLD = 10  # consolida a cada 10 experiências

    def __init__(self, agent_name: str):
        ensure_multi_agent_schema()
        self.agent_name = agent_name

    # ----------------------------------------------------------------------
    # Adicionar memórias
    # ----------------------------------------------------------------------

    def add_core(self, key: str, content: str, relevance: int = 10) -> None:
        """Adiciona fato fundamental (sempre no contexto)."""
        self._add(MemoryLevel.CORE, key, content, relevance=relevance)

    def add_learned(self, key: str, content: str,
                    context: Optional[str] = None,
                    relevance: int = 5) -> None:
        """Adiciona padrão aprendido."""
        self._add(MemoryLevel.LEARNED, key, content,
                  context=context, relevance=relevance)

    def add_episodic(self, content: str,
                     context: Optional[str] = None) -> None:
        """Adiciona experiência episódica (auto-gera key)."""
        key = f"ep_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(content.encode()).hexdigest()[:6]}"
        self._add(MemoryLevel.EPISODIC, key, content,
                  context=context, relevance=3)

        # Verifica se precisa consolidar
        episodic_count = db.fetch_one(
            "SELECT COUNT(*) as n FROM agent_memory WHERE agent_name=? AND level=?",
            (self.agent_name, MemoryLevel.EPISODIC),
        )
        if episodic_count and episodic_count["n"] >= self.CONSOLIDATION_THRESHOLD * 2:
            self._maybe_consolidate()

    def _add(self, level: str, key: str, content: str,
             context: Optional[str] = None, relevance: int = 5) -> None:
        """Interna: adiciona entry em um nível."""
        tokens = len(content) // 4

        db.execute(
            """
            INSERT INTO agent_memory
            (agent_name, level, key, content, context, relevance, tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_name, level, key) DO UPDATE SET
                content = excluded.content,
                context = excluded.context,
                relevance = excluded.relevance,
                tokens = excluded.tokens,
                usage_count = usage_count + 1,
                last_used_at = CURRENT_TIMESTAMP
            """,
            (self.agent_name, level, key, content, context, relevance, tokens),
        )

    # ----------------------------------------------------------------------
    # Recuperar memórias (com budget de tokens)
    # ----------------------------------------------------------------------

    def get_context_for_llm(
        self,
        query: Optional[str] = None,
        token_budget: int = 1500,
    ) -> str:
        """
        Monta o texto de memória a incluir no prompt do agente,
        respeitando o budget de tokens.

        Prioridade: CORE > LEARNED relevante > EPISODIC recente
        """
        parts = []
        tokens_used = 0

        # 1. CORE (sempre incluir, sem limite aqui)
        core_rows = db.fetch_all(
            """
            SELECT * FROM agent_memory
            WHERE agent_name = ? AND level = ?
            ORDER BY relevance DESC
            """,
            (self.agent_name, MemoryLevel.CORE),
        )
        if core_rows:
            parts.append("## Memória fundamental")
            for row in core_rows:
                line = f"- {row['key']}: {row['content']}"
                parts.append(line)
                tokens_used += row["tokens"]

        # 2. LEARNED (por relevância, cabendo no budget)
        budget_remaining = token_budget - tokens_used
        if budget_remaining > 100:
            # Se tiver query, ordena por similaridade textual simples
            if query:
                learned_rows = self._fetch_learned_by_relevance(query)
            else:
                learned_rows = db.fetch_all(
                    """
                    SELECT * FROM agent_memory
                    WHERE agent_name = ? AND level = ?
                    ORDER BY relevance DESC, usage_count DESC
                    LIMIT 20
                    """,
                    (self.agent_name, MemoryLevel.LEARNED),
                )

            if learned_rows:
                parts.append("\n## Padrões aprendidos")
                for row in learned_rows:
                    if tokens_used + row["tokens"] > token_budget - 200:
                        break
                    parts.append(f"- {row['content']}")
                    tokens_used += row["tokens"]
                    # Incrementa contador de uso
                    db.execute(
                        "UPDATE agent_memory SET usage_count = usage_count + 1, "
                        "last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (row["id"],),
                    )

        # 3. EPISODIC recente (últimas 3 se sobrar budget)
        budget_remaining = token_budget - tokens_used
        if budget_remaining > 200:
            ep_rows = db.fetch_all(
                """
                SELECT * FROM agent_memory
                WHERE agent_name = ? AND level = ?
                ORDER BY created_at DESC LIMIT 3
                """,
                (self.agent_name, MemoryLevel.EPISODIC),
            )
            if ep_rows:
                parts.append("\n## Experiências recentes")
                for row in ep_rows:
                    if tokens_used + row["tokens"] > token_budget:
                        break
                    parts.append(f"- {row['content'][:200]}")
                    tokens_used += min(row["tokens"], 50)

        return "\n".join(parts) if parts else ""

    def _fetch_learned_by_relevance(self, query: str,
                                     limit: int = 10) -> list[dict]:
        """
        Busca memórias LEARNED por palavra-chave simples.
        (Busca semântica real via embedding fica para versão futura.)
        """
        words = [w for w in query.lower().split() if len(w) > 3]
        if not words:
            return []

        clauses = " OR ".join(["LOWER(content) LIKE ?" for _ in words])
        params = [self.agent_name, MemoryLevel.LEARNED] + [f"%{w}%" for w in words]

        return db.fetch_all(
            f"""
            SELECT * FROM agent_memory
            WHERE agent_name = ? AND level = ?
              AND ({clauses})
            ORDER BY relevance DESC, usage_count DESC LIMIT ?
            """,
            tuple(params) + (limit,),
        )

    # ----------------------------------------------------------------------
    # Consolidação (destila experiências em padrões)
    # ----------------------------------------------------------------------

    def _maybe_consolidate(self) -> None:
        """
        Se tem muita memória episódica, usa um modelo BARATO para
        destilar em padrões LEARNED e arquivar episódicas antigas.
        """
        from backend.llm.router import router, LLMRequest
        from backend.core.config import TaskComplexity

        # Pega episódicas para consolidar (mais antigas primeiro)
        rows = db.fetch_all(
            """
            SELECT * FROM agent_memory
            WHERE agent_name = ? AND level = ?
            ORDER BY created_at ASC LIMIT ?
            """,
            (self.agent_name, MemoryLevel.EPISODIC, self.CONSOLIDATION_THRESHOLD),
        )

        if len(rows) < self.CONSOLIDATION_THRESHOLD:
            return

        experiences = "\n".join([f"- {r['content']}" for r in rows])
        ids_being_consolidated = [str(r["id"]) for r in rows]

        prompt = f"""Analise estas {len(rows)} experiências de um agente e extraia 1-3 PADRÕES REUTILIZÁVEIS que o agente pode aprender.

Cada padrão deve ser:
- GENÉRICO (aplicável a situações futuras, não específico a um caso)
- CURTO (1-2 frases)
- ACIONÁVEL (diz o que fazer, não apenas o que aconteceu)

Experiências:
{experiences}

Formato de saída (um por linha, sem numeração):
padrão1
padrão2
..."""

        try:
            response = router.route(LLMRequest(
                prompt=prompt,
                complexity_hint=TaskComplexity.SIMPLE,
                temperature=0.2,
                max_tokens=300,
            ))

            if response.error or not response.content:
                return

            # Salva cada padrão extraído como LEARNED
            patterns = [p.strip("- ").strip() for p in response.content.split("\n")
                        if p.strip() and not p.strip().startswith("#")]

            for i, pattern in enumerate(patterns[:3]):
                if not pattern or len(pattern) < 10:
                    continue
                key = f"pattern_{datetime.now().strftime('%Y%m%d')}_{i}"
                self.add_learned(
                    key=key,
                    content=pattern,
                    context=f"Consolidado de {len(rows)} experiências",
                    relevance=6,
                )

            # Registra no log de aprendizado
            db.execute(
                """
                INSERT INTO learning_log (agent_name, task_summary, extracted, stored_as)
                VALUES (?, ?, ?, 'learned')
                """,
                (self.agent_name,
                 f"Consolidação de {len(rows)} experiências",
                 response.content[:500]),
            )

            # Remove as episódicas consolidadas
            placeholders = ",".join("?" * len(ids_being_consolidated))
            db.execute(
                f"DELETE FROM agent_memory WHERE id IN ({placeholders})",
                tuple(ids_being_consolidated),
            )
        except Exception:
            # Falha na consolidação não é crítico, pode tentar depois
            pass

    # ----------------------------------------------------------------------
    # Limpeza
    # ----------------------------------------------------------------------

    def prune_unused_learned(self, days_threshold: int = 30) -> int:
        """Remove padrões LEARNED que não foram usados em N dias."""
        threshold = (datetime.now() - timedelta(days=days_threshold)).isoformat()
        cursor = db.execute(
            """
            DELETE FROM agent_memory
            WHERE agent_name = ? AND level = ?
              AND usage_count = 0
              AND (last_used_at IS NULL OR last_used_at < ?)
            """,
            (self.agent_name, MemoryLevel.LEARNED, threshold),
        )
        return cursor.rowcount

    def stats(self) -> dict:
        """Estatísticas da memória deste agente."""
        result = {}
        for level in (MemoryLevel.CORE, MemoryLevel.LEARNED, MemoryLevel.EPISODIC):
            row = db.fetch_one(
                """
                SELECT COUNT(*) as n, COALESCE(SUM(tokens), 0) as total_tokens
                FROM agent_memory WHERE agent_name = ? AND level = ?
                """,
                (self.agent_name, level),
            )
            result[level] = {
                "entries": row["n"] if row else 0,
                "tokens": row["total_tokens"] if row else 0,
            }
        return result


# ==========================================================================
# SHARED MEMORY BUS
# ==========================================================================

class SharedMemoryBus:
    """
    Canal de memória compartilhada entre agentes.

    Uso típico:
      1. Agente principal analisa algo e coloca contexto no bus:
           bus.publish(namespace="project:gymflow", key="schema_decisions",
                       content="...", source="main")

      2. Sub-agente criado para revisar código do GymFlow consulta:
           context = bus.fetch(namespace="project:gymflow", agent="code-reviewer")

      3. O sub-agente só recebe memórias DO PROJETO, não tudo.

    Namespaces sugeridos:
      - 'project:<nome>'  memórias ligadas a um projeto
      - 'task:<id>'       memórias específicas de uma tarefa ativa
      - 'entity:<nome>'   tudo sobre uma pessoa/empresa
      - 'skill:<nome>'    skills e como usá-las
    """

    @staticmethod
    def publish(
        namespace: str,
        key: str,
        content: str,
        source_agent: Optional[str] = None,
        target_agents: Optional[list[str]] = None,
        ttl_hours: Optional[int] = None,
    ) -> int:
        """Publica uma memória no canal compartilhado."""
        ensure_multi_agent_schema()

        expires_at = None
        if ttl_hours:
            expires_at = (datetime.now() + timedelta(hours=ttl_hours)).isoformat()

        tokens = len(content) // 4
        targets_json = json.dumps(target_agents) if target_agents else None

        cursor = db.execute(
            """
            INSERT INTO shared_memory
            (namespace, key, content, source_agent, target_agents,
             expires_at, tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(namespace, key) DO UPDATE SET
                content = excluded.content,
                source_agent = excluded.source_agent,
                target_agents = excluded.target_agents,
                expires_at = excluded.expires_at,
                tokens = excluded.tokens
            """,
            (namespace, key, content, source_agent, targets_json,
             expires_at, tokens),
        )
        return cursor.lastrowid

    @staticmethod
    def fetch(
        namespace: str,
        agent: Optional[str] = None,
        token_budget: int = 1000,
    ) -> str:
        """
        Busca todas as memórias de um namespace acessíveis por `agent`.
        Monta string pronta para injetar no contexto do LLM.
        """
        # Remove expiradas
        db.execute(
            "DELETE FROM shared_memory WHERE expires_at IS NOT NULL "
            "AND expires_at < CURRENT_TIMESTAMP"
        )

        rows = db.fetch_all(
            """
            SELECT * FROM shared_memory
            WHERE namespace = ?
            ORDER BY created_at DESC
            """,
            (namespace,),
        )

        if not rows:
            return ""

        # Filtra por agente alvo
        accessible = []
        for row in rows:
            targets = row.get("target_agents")
            if targets:
                try:
                    target_list = json.loads(targets)
                    if agent and agent not in target_list:
                        continue
                except Exception:
                    pass
            accessible.append(row)

        # Respeita budget de tokens
        parts = [f"## Memória compartilhada ({namespace})"]
        tokens_used = 0
        for row in accessible:
            if tokens_used + row["tokens"] > token_budget:
                break
            parts.append(f"- [{row['key']}] {row['content']}")
            tokens_used += row["tokens"]

        return "\n".join(parts)

    @staticmethod
    def forward(
        from_namespace: str,
        to_namespace: str,
        keys: Optional[list[str]] = None,
    ) -> int:
        """
        Encaminha memórias de um namespace para outro.
        Útil quando agente principal passa contexto para sub-agente.

        Ex: bus.forward("project:gymflow", "task:review-pr-123")
        """
        if keys:
            placeholders = ",".join("?" * len(keys))
            rows = db.fetch_all(
                f"SELECT * FROM shared_memory "
                f"WHERE namespace = ? AND key IN ({placeholders})",
                (from_namespace, *keys),
            )
        else:
            rows = db.fetch_all(
                "SELECT * FROM shared_memory WHERE namespace = ?",
                (from_namespace,),
            )

        count = 0
        for row in rows:
            SharedMemoryBus.publish(
                namespace=to_namespace,
                key=row["key"],
                content=row["content"],
                source_agent=row["source_agent"],
            )
            count += 1
        return count

    @staticmethod
    def list_namespaces() -> list[dict]:
        """Lista todos os namespaces ativos e estatísticas."""
        return db.fetch_all(
            """
            SELECT namespace,
                   COUNT(*) as entries,
                   SUM(tokens) as total_tokens,
                   MAX(created_at) as last_updated
            FROM shared_memory
            GROUP BY namespace
            ORDER BY last_updated DESC
            """
        )


# ==========================================================================
# LEARNING LOOP (integração com roteador)
# ==========================================================================

class LearningLoop:
    """
    Após cada tarefa bem-sucedida, extrai aprendizado e salva na
    memória do agente. Inspirado no loop do Hermes:
    execute → evaluate → extract → refine → retrieve.
    """

    @staticmethod
    def learn_from_interaction(
        agent_name: str,
        user_input: str,
        agent_response: str,
        success: bool = True,
    ) -> Optional[str]:
        """
        Após uma interação, decide se há algo a aprender.
        Se sim, chama um modelo barato para extrair e salvar.
        """
        if not success or len(user_input) + len(agent_response) < 200:
            return None

        from backend.llm.router import router, LLMRequest
        from backend.core.config import TaskComplexity

        memory = ProgressiveAgentMemory(agent_name)

        # Sempre salva como episódica (barato, é só INSERT)
        episode = f"User: {user_input[:200]}\nAgent: {agent_response[:300]}"
        memory.add_episodic(content=episode)

        # Periodicamente, a consolidação é chamada automaticamente
        # dentro do add_episodic. Não precisa forçar aqui.

        return "episodic-saved"


# ==========================================================================
# INSTÂNCIA GLOBAL
# ==========================================================================

shared_bus = SharedMemoryBus()


def get_agent_memory(agent_name: str) -> ProgressiveAgentMemory:
    """Factory para obter memória de um agente específico."""
    return ProgressiveAgentMemory(agent_name)
