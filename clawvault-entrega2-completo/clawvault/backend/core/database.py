"""
ClawVault - Camada de Banco de Dados
=====================================

Usa SQLite direto (sem ORM pesado) para ficar simples e rápido.
O banco armazena:
- Conversas e mensagens (memória morna)
- Resumos de conversas antigas
- Uso de tokens e custos (para controle de orçamento)
- Skills importadas do OpenClaw
- Embeddings para busca semântica
"""

import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from backend.core.config import DB_PATH


# ==========================================================================
# SCHEMA DO BANCO
# ==========================================================================

SCHEMA_SQL = """
-- Conversas (sessões de chat com o agente)
CREATE TABLE IF NOT EXISTS conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid            TEXT UNIQUE NOT NULL,
    title           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_name      TEXT DEFAULT 'default',
    archived        INTEGER DEFAULT 0,
    summary         TEXT,
    total_tokens    INTEGER DEFAULT 0,
    total_cost_usd  REAL DEFAULT 0.0
);

-- Mensagens individuais dentro de cada conversa
CREATE TABLE IF NOT EXISTS messages (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id   INTEGER NOT NULL,
    role              TEXT NOT NULL,     -- user, assistant, system, tool
    content           TEXT NOT NULL,
    model_used        TEXT,
    complexity        TEXT,              -- TRIVIAL, SIMPLE, MEDIUM, COMPLEX, CRITICAL
    input_tokens      INTEGER DEFAULT 0,
    output_tokens     INTEGER DEFAULT 0,
    cached_tokens     INTEGER DEFAULT 0,
    cost_usd          REAL DEFAULT 0.0,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata_json     TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(created_at);

-- Registro detalhado de uso (para dashboard e controle de orçamento)
CREATE TABLE IF NOT EXISTS usage_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_id        TEXT NOT NULL,
    provider        TEXT NOT NULL,
    operation       TEXT,                -- chat, embedding, classification, summarization
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cached_tokens   INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0.0,
    success         INTEGER DEFAULT 1,
    error_message   TEXT,
    conversation_id INTEGER,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX IF NOT EXISTS idx_usage_date ON usage_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_model ON usage_log(model_id);

-- Resumos de conversas arquivadas (camada FRIA)
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL UNIQUE,
    summary         TEXT NOT NULL,
    key_points      TEXT,                -- JSON array
    entities        TEXT,                -- JSON array (pessoas, projetos mencionados)
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- Embeddings para busca semântica (memória FRIA)
CREATE TABLE IF NOT EXISTS embeddings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type     TEXT NOT NULL,       -- message, note, summary
    source_id       INTEGER,
    file_path       TEXT,                -- para notas do vault
    chunk_text      TEXT NOT NULL,
    embedding_blob  BLOB NOT NULL,       -- vetor serializado
    model_used      TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_embeddings_type ON embeddings(source_type);

-- Skills/agentes importados
CREATE TABLE IF NOT EXISTS skills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT UNIQUE NOT NULL,
    description     TEXT,
    prompt_template TEXT NOT NULL,
    preferred_model TEXT,
    tools_json      TEXT,                -- JSON array de tools
    source          TEXT,                -- 'openclaw', 'native', 'custom'
    enabled         INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cache de respostas (evita chamadas repetidas)
CREATE TABLE IF NOT EXISTS response_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key       TEXT UNIQUE NOT NULL,  -- hash do prompt + modelo
    prompt_hash     TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    response        TEXT NOT NULL,
    tokens_saved    INTEGER DEFAULT 0,
    hits            INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cache_key ON response_cache(cache_key);

-- Orçamento mensal (para controle de gastos)
CREATE TABLE IF NOT EXISTS monthly_budget (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    year_month      TEXT UNIQUE NOT NULL,  -- 'YYYY-MM'
    budget_usd      REAL NOT NULL,
    spent_usd       REAL DEFAULT 0.0,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Configurações dinâmicas (chave-valor)
CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


# ==========================================================================
# GERENCIADOR DE CONEXÃO
# ==========================================================================

class Database:
    """Gerencia conexão com o SQLite. Thread-safe via context manager."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._initialized = False

    def initialize(self) -> None:
        """Cria o banco e todas as tabelas se não existirem."""
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        self._initialized = True

    @contextmanager
    def connect(self):
        """Context manager que retorna uma conexão SQLite."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=30.0,
        )
        conn.row_factory = sqlite3.Row  # Permite acesso por nome de coluna
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")  # Melhor performance
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Executa um comando e faz commit."""
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Busca uma linha. Retorna None se não encontrar."""
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Busca todas as linhas."""
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]


# Instância global
db = Database()


# ==========================================================================
# HELPERS DE USO COMUM
# ==========================================================================

def record_usage(
    model_id: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    operation: str = "chat",
    cached_tokens: int = 0,
    conversation_id: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
) -> None:
    """Registra uso de API para tracking de custo."""
    db.execute(
        """
        INSERT INTO usage_log
        (model_id, provider, operation, input_tokens, output_tokens,
         cached_tokens, cost_usd, success, error_message, conversation_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            model_id, provider, operation, input_tokens, output_tokens,
            cached_tokens, cost_usd, int(success), error_message, conversation_id,
        ),
    )
    # Atualiza orçamento do mês atual
    year_month = datetime.now().strftime("%Y-%m")
    db.execute(
        """
        INSERT INTO monthly_budget (year_month, budget_usd, spent_usd)
        VALUES (?, 50.0, ?)
        ON CONFLICT(year_month) DO UPDATE SET
            spent_usd = spent_usd + excluded.spent_usd,
            updated_at = CURRENT_TIMESTAMP
        """,
        (year_month, cost_usd),
    )


def get_monthly_spend() -> dict:
    """Retorna gastos do mês atual."""
    year_month = datetime.now().strftime("%Y-%m")
    row = db.fetch_one(
        "SELECT * FROM monthly_budget WHERE year_month = ?",
        (year_month,),
    )
    if not row:
        return {"year_month": year_month, "spent_usd": 0.0, "budget_usd": 50.0}
    return row


def get_setting(key: str, default: Any = None) -> Any:
    """Lê uma configuração dinâmica."""
    row = db.fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return row["value"]


def set_setting(key: str, value: Any) -> None:
    """Salva uma configuração dinâmica."""
    serialized = json.dumps(value) if not isinstance(value, str) else value
    db.execute(
        """
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                       updated_at = CURRENT_TIMESTAMP
        """,
        (key, serialized),
    )
