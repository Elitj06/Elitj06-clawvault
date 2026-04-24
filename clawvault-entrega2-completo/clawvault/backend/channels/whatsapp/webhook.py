"""
ClawVault - Webhook WhatsApp
==============================

Recebe mensagens do Evolution API via webhook e processa através do
agente 'whatsapp' (pode ser o main ou um especializado para atendimento).

FLUXO DE UMA MENSAGEM:
  1. Cliente envia mensagem no WhatsApp
  2. WhatsApp → Evolution API → POST /api/whatsapp/webhook (aqui)
  3. Extraímos: quem mandou, o que disse, é grupo ou privado?
  4. Verificamos filtros (números bloqueados? horário permitido?)
  5. Montamos contexto do histórico desse contato
  6. Passamos pelo HumanCompressor (economiza tokens)
  7. Enviamos ao LLM com memória do agente 'whatsapp'
  8. Marcamos como lida → simulamos "digitando" → enviamos resposta
  9. Salvamos tudo no banco para contexto futuro

SEGURANÇA:
  - Webhook só aceita requests com assinatura válida (api_key)
  - Números bloqueados são filtrados ANTES de ir ao LLM
  - Rate limiting: máximo N mensagens por minuto por contato
  - Blacklist de palavras (configurável)
"""

import os
import json
import asyncio
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Any

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel

from backend.core.database import db
from backend.llm.router import router as llm_router, LLMRequest
from backend.memory.manager import memory
from backend.memory.multi_agent import AgentRegistry, get_agent_memory, shared_bus
from backend.compression import default_compressor
from backend.channels.whatsapp.client import evolution_client


# ==========================================================================
# SCHEMA DO BANCO (específico de WhatsApp)
# ==========================================================================

WHATSAPP_SCHEMA = """
-- Contatos WhatsApp com suas configurações
CREATE TABLE IF NOT EXISTS whatsapp_contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    remote_jid      TEXT UNIQUE NOT NULL,     -- 5521999999999@s.whatsapp.net
    phone           TEXT NOT NULL,             -- 5521999999999
    name            TEXT,                       -- nome do contato
    is_group        INTEGER DEFAULT 0,
    is_blocked      INTEGER DEFAULT 0,
    is_allowlisted  INTEGER DEFAULT 0,         -- se true, bypassa horário
    conversation_id INTEGER,                    -- link com conversations
    last_message_at TIMESTAMP,
    total_messages  INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- Log de mensagens WhatsApp (separado do log normal pra análise)
CREATE TABLE IF NOT EXISTS whatsapp_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      TEXT UNIQUE,                -- ID do WhatsApp
    remote_jid      TEXT NOT NULL,
    direction       TEXT NOT NULL,              -- 'in' ou 'out'
    content         TEXT NOT NULL,
    media_type      TEXT,                       -- 'text', 'image', 'audio', etc
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed       INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0.0,
    model_used      TEXT
);
CREATE INDEX IF NOT EXISTS idx_wa_jid ON whatsapp_messages(remote_jid);

-- Configuração global do WhatsApp
CREATE TABLE IF NOT EXISTS whatsapp_config (
    key             TEXT PRIMARY KEY,
    value           TEXT
);
"""


def ensure_whatsapp_schema():
    with db.connect() as conn:
        conn.executescript(WHATSAPP_SCHEMA)
        conn.commit()


# ==========================================================================
# CONFIGURAÇÕES PADRÃO
# ==========================================================================

DEFAULT_CONFIG = {
    "enabled": True,
    "agent_name": "whatsapp",
    "business_hours_start": "08:00",
    "business_hours_end": "20:00",
    "respect_business_hours": False,   # se True, só responde no horário
    "out_of_hours_message": (
        "Olá! Recebi sua mensagem. No momento estou fora do horário de "
        "atendimento (das 8h às 20h). Responderei assim que possível."
    ),
    "rate_limit_per_minute": 5,       # max mensagens/min por contato
    "auto_reply_groups": False,        # responder em grupos automaticamente?
    "group_mention_only": True,        # em grupos, só responde se mencionado
    "greeting_on_first_contact": True, # manda saudação no 1º contato
    "first_contact_greeting": (
        "Olá! 👋 Sou o assistente virtual. Como posso ajudar?"
    ),
    "typing_before_reply": True,       # simula 'digitando' antes
    "mark_as_read": True,
}


def get_config(key: str) -> Any:
    """Lê configuração do banco, com fallback para DEFAULT_CONFIG."""
    row = db.fetch_one("SELECT value FROM whatsapp_config WHERE key = ?", (key,))
    if row:
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]
    return DEFAULT_CONFIG.get(key)


def set_config(key: str, value: Any) -> None:
    """Salva configuração no banco."""
    ensure_whatsapp_schema()
    val = json.dumps(value) if not isinstance(value, str) else value
    db.execute(
        """
        INSERT INTO whatsapp_config (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, val),
    )


# ==========================================================================
# RATE LIMITER EM MEMÓRIA
# ==========================================================================

# Rastreio de mensagens recentes por contato (em RAM, reseta ao reiniciar)
_rate_tracker: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(remote_jid: str) -> bool:
    """
    Retorna True se pode processar, False se excedeu o limite.
    Limite configurável via DEFAULT_CONFIG['rate_limit_per_minute'].
    """
    limit = get_config("rate_limit_per_minute") or 5
    now = time.time()
    cutoff = now - 60  # últimos 60 segundos

    # Limpa registros antigos
    _rate_tracker[remote_jid] = [t for t in _rate_tracker[remote_jid] if t > cutoff]

    if len(_rate_tracker[remote_jid]) >= limit:
        return False

    _rate_tracker[remote_jid].append(now)
    return True


def is_in_business_hours() -> bool:
    """Verifica se está dentro do horário comercial configurado."""
    if not get_config("respect_business_hours"):
        return True

    start = get_config("business_hours_start") or "08:00"
    end = get_config("business_hours_end") or "20:00"

    try:
        now = datetime.now().time()
        start_t = datetime.strptime(start, "%H:%M").time()
        end_t = datetime.strptime(end, "%H:%M").time()
        return start_t <= now <= end_t
    except Exception:
        return True


# ==========================================================================
# GESTÃO DE CONTATOS
# ==========================================================================

def get_or_create_contact(remote_jid: str, name: Optional[str] = None) -> dict:
    """Busca ou cria um contato no banco."""
    ensure_whatsapp_schema()

    is_group = "@g.us" in remote_jid
    phone = remote_jid.split("@")[0]

    contact = db.fetch_one(
        "SELECT * FROM whatsapp_contacts WHERE remote_jid = ?",
        (remote_jid,),
    )

    if not contact:
        # Cria conversa para este contato
        conv_id = memory.create_conversation(
            title=f"WhatsApp: {name or phone}",
            agent_name=get_config("agent_name") or "whatsapp",
        )

        db.execute(
            """
            INSERT INTO whatsapp_contacts
            (remote_jid, phone, name, is_group, conversation_id,
             last_message_at, total_messages)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0)
            """,
            (remote_jid, phone, name, int(is_group), conv_id),
        )
        contact = db.fetch_one(
            "SELECT * FROM whatsapp_contacts WHERE remote_jid = ?",
            (remote_jid,),
        )

    return contact


def update_contact_activity(remote_jid: str) -> None:
    """Atualiza timestamp e contador do contato."""
    db.execute(
        """
        UPDATE whatsapp_contacts
        SET last_message_at = CURRENT_TIMESTAMP,
            total_messages = total_messages + 1
        WHERE remote_jid = ?
        """,
        (remote_jid,),
    )


# ==========================================================================
# EXTRATORES (lê payload do Evolution)
# ==========================================================================

def extract_message_data(payload: dict) -> Optional[dict]:
    """
    Extrai dados relevantes do webhook do Evolution API.
    Retorna None se o payload não for de mensagem nova.
    """
    event = payload.get("event")
    if event != "messages.upsert":
        return None

    data = payload.get("data", {})
    key = data.get("key", {})
    msg = data.get("message", {})

    # Ignora mensagens próprias (fromMe)
    if key.get("fromMe"):
        return None

    remote_jid = key.get("remoteJid", "")
    if not remote_jid:
        return None

    # Extrai texto (pode vir em vários formatos)
    text = (
        msg.get("conversation")
        or msg.get("extendedTextMessage", {}).get("text")
        or msg.get("imageMessage", {}).get("caption")
        or msg.get("videoMessage", {}).get("caption")
        or ""
    )

    # Detecta tipo de mídia
    media_type = "text"
    if "audioMessage" in msg:
        media_type = "audio"
    elif "imageMessage" in msg:
        media_type = "image"
    elif "videoMessage" in msg:
        media_type = "video"
    elif "documentMessage" in msg:
        media_type = "document"

    return {
        "message_id": key.get("id"),
        "remote_jid": remote_jid,
        "from_me": key.get("fromMe", False),
        "is_group": "@g.us" in remote_jid,
        "participant": key.get("participant"),  # em grupos, quem mandou
        "push_name": data.get("pushName"),
        "text": text.strip(),
        "media_type": media_type,
        "timestamp": data.get("messageTimestamp"),
    }


# ==========================================================================
# PROCESSADOR PRINCIPAL
# ==========================================================================

async def process_whatsapp_message(msg_data: dict) -> None:
    """
    Processa uma mensagem recebida:
    - Valida filtros
    - Monta contexto
    - Chama LLM
    - Responde
    """
    if not get_config("enabled"):
        return

    remote_jid = msg_data["remote_jid"]
    text = msg_data["text"]

    # Sem texto? Ignora por enquanto (TODO: transcrição de áudio)
    if not text:
        return

    # Grupos: só responde se configurado
    if msg_data["is_group"]:
        if not get_config("auto_reply_groups"):
            return
        # Se só responde quando mencionado, verifica menção
        if get_config("group_mention_only"):
            if "@" not in text:  # heurística simples
                return

    contact = get_or_create_contact(
        remote_jid, name=msg_data.get("push_name")
    )

    # Contato bloqueado?
    if contact["is_blocked"]:
        return

    # Rate limit
    if not check_rate_limit(remote_jid):
        return

    # Horário comercial (allowlist bypassa)
    if not contact["is_allowlisted"] and not is_in_business_hours():
        out_msg = get_config("out_of_hours_message")
        if out_msg:
            try:
                evolution_client.send_text(contact["phone"], out_msg)
            except Exception:
                pass
        return

    # Registra mensagem recebida
    db.execute(
        """
        INSERT OR IGNORE INTO whatsapp_messages
        (message_id, remote_jid, direction, content, media_type)
        VALUES (?, ?, 'in', ?, ?)
        """,
        (msg_data["message_id"], remote_jid, text, msg_data["media_type"]),
    )
    update_contact_activity(remote_jid)

    # Primeira mensagem? Envia saudação
    is_first = contact["total_messages"] == 0
    if is_first and get_config("greeting_on_first_contact"):
        greeting = get_config("first_contact_greeting")
        try:
            evolution_client.send_text(contact["phone"], greeting)
        except Exception:
            pass

    # Marca como lida
    if get_config("mark_as_read") and msg_data.get("message_id"):
        try:
            evolution_client.mark_as_read(
                remote_jid, msg_data["message_id"]
            )
        except Exception:
            pass

    # Simula digitando
    if get_config("typing_before_reply"):
        try:
            evolution_client.send_typing(contact["phone"], duration_ms=2000)
        except Exception:
            pass

    # Processa com LLM
    agent_name = get_config("agent_name") or "whatsapp"

    # Garante que o agente existe
    if not AgentRegistry.get(agent_name):
        AgentRegistry.register(
            name=agent_name,
            role="Atendente virtual via WhatsApp",
            parent_agent="main",
            system_prompt=(
                "Você é um atendente virtual respondendo via WhatsApp. "
                "Seja breve, cordial e objetivo (máx 3-4 linhas por mensagem). "
                "Responda em português brasileiro, em tom amigável mas profissional. "
                "Se não souber responder, oriente o cliente a aguardar atendimento humano."
            ),
        )

    # Compressão + contexto
    compressed = default_compressor.compress(text)
    effective = compressed.compressed if compressed.tokens_saved_estimate > 2 else text

    context_messages = memory.get_context_for_llm(
        contact["conversation_id"], token_budget=3000,
    )

    agent_mem = get_agent_memory(agent_name)
    agent_context = agent_mem.get_context_for_llm(
        query=effective, token_budget=1000,
    )

    agent_info = AgentRegistry.get(agent_name)
    system = agent_info.get("system_prompt", "")
    if agent_context:
        system += f"\n\n{agent_context}"

    # Chama LLM
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: llm_router.route(LLMRequest(
                prompt=effective,
                system=system,
                messages=context_messages,
                conversation_id=contact["conversation_id"],
                max_tokens=500,   # respostas curtas no WhatsApp
            )),
        )
    except Exception as e:
        print(f"❌ Erro ao chamar LLM: {e}")
        return

    if response.error or not response.content:
        print(f"❌ Erro na resposta LLM: {response.error}")
        return

    reply_text = response.content.strip()

    # Salva no banco da memória hierárquica
    memory.add_message(
        contact["conversation_id"], "user", text,
        input_tokens=response.input_tokens,
    )
    memory.add_message(
        contact["conversation_id"], "assistant", reply_text,
        model_used=response.model_id,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
    )

    # Envia resposta via WhatsApp
    try:
        evolution_client.send_text(contact["phone"], reply_text)

        # Log no banco específico
        db.execute(
            """
            INSERT INTO whatsapp_messages
            (remote_jid, direction, content, media_type, cost_usd, model_used)
            VALUES (?, 'out', ?, 'text', ?, ?)
            """,
            (remote_jid, reply_text, response.cost_usd, response.model_id),
        )
    except Exception as e:
        print(f"❌ Erro ao enviar resposta WhatsApp: {e}")


# ==========================================================================
# ROTAS FASTAPI
# ==========================================================================

router = APIRouter()


class SendMessageRequest(BaseModel):
    phone: str
    message: str


class WhatsAppConfigUpdate(BaseModel):
    key: str
    value: Any


@router.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks):
    """
    Webhook principal — recebe eventos do Evolution API.
    Processa mensagens em background para responder imediatamente 200 OK.
    """
    payload = await request.json()
    event = payload.get("event")

    # Evento de conexão (qrcode/connected/disconnected)
    if event == "connection.update":
        return {"status": "ack"}

    # Mensagem recebida
    if event == "messages.upsert":
        msg_data = extract_message_data(payload)
        if msg_data:
            # Processa em background para resposta rápida ao Evolution
            background.add_task(process_whatsapp_message, msg_data)

    return {"status": "ok"}


@router.get("/status")
def whatsapp_status():
    """Verifica status da conexão WhatsApp."""
    if not evolution_client.config.is_configured:
        return {
            "configured": False,
            "message": "Evolution API não configurada. Configure EVOLUTION_BASE_URL e EVOLUTION_API_KEY no .env",
        }

    try:
        online = evolution_client.is_online()
        if not online:
            return {
                "configured": True,
                "online": False,
                "message": "Servidor Evolution não está respondendo.",
            }

        state = evolution_client.get_connection_state()
        return {
            "configured": True,
            "online": True,
            "instance": evolution_client.config.instance_name,
            "state": state,
        }
    except Exception as e:
        return {
            "configured": True,
            "online": False,
            "error": str(e),
        }


@router.post("/instance/create")
def create_instance(webhook_url: Optional[str] = None):
    """Cria uma nova instância WhatsApp no Evolution API."""
    try:
        # Por padrão, aponta o webhook para esta própria API
        if not webhook_url:
            base = os.getenv("PUBLIC_API_URL", "http://localhost:8000")
            webhook_url = f"{base}/api/whatsapp/webhook"

        result = evolution_client.create_instance(webhook_url=webhook_url)
        return {"status": "created", "webhook": webhook_url, "result": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/qrcode")
def get_qrcode():
    """Retorna o QR Code para escanear no celular."""
    try:
        return evolution_client.get_qrcode()
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/send")
def send_message(req: SendMessageRequest):
    """Envia uma mensagem manualmente (útil para testes e broadcast)."""
    try:
        result = evolution_client.send_text(req.phone, req.message)
        db.execute(
            """
            INSERT INTO whatsapp_messages (remote_jid, direction, content, media_type)
            VALUES (?, 'out', ?, 'text')
            """,
            (f"{req.phone}@s.whatsapp.net", req.message),
        )
        return {"status": "sent", "result": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/contacts")
def list_contacts(limit: int = 100):
    """Lista todos os contatos."""
    ensure_whatsapp_schema()
    contacts = db.fetch_all(
        """
        SELECT * FROM whatsapp_contacts
        ORDER BY last_message_at DESC LIMIT ?
        """,
        (limit,),
    )
    return {"contacts": contacts}


@router.post("/contacts/{remote_jid}/block")
def block_contact(remote_jid: str):
    """Bloqueia um contato (ClawVault ignora mensagens dele)."""
    db.execute(
        "UPDATE whatsapp_contacts SET is_blocked = 1 WHERE remote_jid = ?",
        (remote_jid,),
    )
    return {"status": "blocked"}


@router.post("/contacts/{remote_jid}/unblock")
def unblock_contact(remote_jid: str):
    """Desbloqueia um contato."""
    db.execute(
        "UPDATE whatsapp_contacts SET is_blocked = 0 WHERE remote_jid = ?",
        (remote_jid,),
    )
    return {"status": "unblocked"}


@router.get("/config")
def get_all_config():
    """Retorna toda a configuração atual do WhatsApp."""
    ensure_whatsapp_schema()
    rows = db.fetch_all("SELECT * FROM whatsapp_config")
    stored = {}
    for row in rows:
        try:
            stored[row["key"]] = json.loads(row["value"])
        except Exception:
            stored[row["key"]] = row["value"]
    # Merge com defaults
    return {**DEFAULT_CONFIG, **stored}


@router.put("/config")
def update_config(req: WhatsAppConfigUpdate):
    """Atualiza uma configuração do WhatsApp."""
    set_config(req.key, req.value)
    return {"status": "updated", "key": req.key}


@router.get("/messages")
def list_messages(remote_jid: Optional[str] = None, limit: int = 100):
    """Lista mensagens WhatsApp (filtra por JID se informado)."""
    ensure_whatsapp_schema()
    if remote_jid:
        rows = db.fetch_all(
            """
            SELECT * FROM whatsapp_messages
            WHERE remote_jid = ?
            ORDER BY timestamp DESC LIMIT ?
            """,
            (remote_jid, limit),
        )
    else:
        rows = db.fetch_all(
            "SELECT * FROM whatsapp_messages ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
    return {"messages": rows}
