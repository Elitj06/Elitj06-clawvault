"""
ClawVault - Servidor FastAPI
==============================

Servidor central que expõe:
- API REST para o dashboard web
- WebSocket para streaming de chat em tempo real
- Webhooks para receber mensagens do WhatsApp (Evolution API)

Execução:
    python -m backend.api.server
    (ou)
    uvicorn backend.api.server:app --reload --port 8000

Por padrão roda em http://localhost:8000
Docs interativas em http://localhost:8000/docs
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# Carrega .env antes de tudo
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from backend.core.config import MODELS_CATALOG, APP_CONFIG, API_KEYS, VAULT_DIR
from backend.core.database import db, get_monthly_spend
from backend.llm.router import router, LLMRequest
from backend.llm.classifier import classifier
from backend.memory.manager import memory
from backend.memory.vault import vault
from backend.memory.multi_agent import (
    AgentRegistry, get_agent_memory, shared_bus,
    ensure_multi_agent_schema,
)
from backend.compression import default_compressor


# ==========================================================================
# LIFECYCLE
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialização do servidor."""
    # Garante que o banco está inicializado
    db.initialize()
    ensure_multi_agent_schema()

    # Registra agente principal se não existir
    if not AgentRegistry.get("main"):
        AgentRegistry.register(
            name="main",
            role="Assistente pessoal principal",
            is_main=True,
        )

    print("🐾 ClawVault API rodando em http://localhost:8000")
    print("📚 Docs em http://localhost:8000/docs")
    yield
    print("👋 Servidor encerrado.")


app = FastAPI(
    title="ClawVault API",
    version=APP_CONFIG.version,
    description="Sistema de agentes multi-LLM com memória persistente",
    lifespan=lifespan,
)

# CORS — permite que o frontend Next.js (localhost:3000) acesse a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================================
# MODELOS PYDANTIC (validação de input/output)
# ==========================================================================

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    agent_name: str = "main"
    model_override: Optional[str] = None
    compress: bool = True


class ChatResponse(BaseModel):
    content: str
    model_id: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    complexity: Optional[str] = None
    conversation_id: int
    compression_savings: int = 0


class ShareMemoryRequest(BaseModel):
    namespace: str
    key: str
    content: str
    source_agent: str = "main"
    target_agents: Optional[list[str]] = None
    ttl_hours: Optional[int] = None


class CreateAgentRequest(BaseModel):
    name: str
    role: str
    parent_agent: str = "main"
    preferred_model: Optional[str] = None
    system_prompt: Optional[str] = None


class SaveNoteRequest(BaseModel):
    title: str
    content: str
    layer: str = "wiki"
    category: str = "conceitos"
    tags: list[str] = []


# ==========================================================================
# ROTAS: STATUS E CONFIGURAÇÃO
# ==========================================================================

@app.get("/")
def root():
    """Health check."""
    return {
        "status": "ok",
        "service": "ClawVault",
        "version": APP_CONFIG.version,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/status")
def get_status():
    """Status geral do sistema."""
    spend = get_monthly_spend()

    providers = {}
    for name in ("anthropic", "openai", "google", "deepseek", "zai",
                 "groq", "moonshot", "minimax", "alibaba", "openrouter"):
        providers[name] = API_KEYS.has_provider(name)

    total_conv = db.fetch_one("SELECT COUNT(*) as n FROM conversations") or {"n": 0}
    total_msg = db.fetch_one("SELECT COUNT(*) as n FROM messages") or {"n": 0}
    total_agents = db.fetch_one("SELECT COUNT(*) as n FROM agents") or {"n": 0}

    return {
        "version": APP_CONFIG.version,
        "providers": providers,
        "budget": {
            "spent_usd": spend["spent_usd"],
            "limit_usd": APP_CONFIG.monthly_budget_usd,
            "percent_used": (spend["spent_usd"] / APP_CONFIG.monthly_budget_usd * 100)
                if APP_CONFIG.monthly_budget_usd else 0,
        },
        "stats": {
            "conversations": total_conv["n"],
            "messages": total_msg["n"],
            "agents": total_agents["n"],
        },
    }


@app.get("/api/models")
def list_models(available_only: bool = False):
    """Lista catálogo de modelos."""
    result = []
    for model in MODELS_CATALOG.values():
        if available_only and not API_KEYS.has_provider(model.provider):
            continue
        result.append({
            "id": model.id,
            "provider": model.provider,
            "tier": model.tier.value,
            "context_window": model.context_window,
            "cost_input": model.cost_input,
            "cost_output": model.cost_output,
            "supports_vision": model.supports_vision,
            "description": model.description,
            "available": API_KEYS.has_provider(model.provider),
        })
    return {"models": result, "total": len(result)}


# ==========================================================================
# ROTAS: CHAT
# ==========================================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Envia uma mensagem e recebe resposta (sync)."""
    # Cria ou usa conversa existente
    conv_id = req.conversation_id
    if not conv_id:
        conv_id = memory.create_conversation(agent_name=req.agent_name)

    # Aplica compressão se habilitada
    effective_input = req.message
    compression_saved = 0
    if req.compress:
        result = default_compressor.compress(req.message)
        if result.tokens_saved_estimate > 2:
            effective_input = result.compressed
            compression_saved = result.tokens_saved_estimate

    # Busca contexto
    context_messages = memory.get_context_for_llm(conv_id, token_budget=4000)

    # Busca memória do agente
    agent_mem = get_agent_memory(req.agent_name)
    agent_context = agent_mem.get_context_for_llm(
        query=effective_input, token_budget=1500,
    )

    # System prompt combinando agente + memória
    agent_info = AgentRegistry.get(req.agent_name)
    system_prompt = (
        (agent_info.get("system_prompt") if agent_info else "")
        or "Você é um assistente prestativo. Responda em português."
    )
    if agent_context:
        system_prompt += f"\n\n{agent_context}"

    # Chama o LLM
    llm_req = LLMRequest(
        prompt=effective_input,
        system=system_prompt,
        messages=context_messages,
        model_override=req.model_override,
        conversation_id=conv_id,
    )
    response = router.route(llm_req)

    if response.error:
        raise HTTPException(status_code=500, detail=response.error)

    # Salva mensagens
    memory.add_message(
        conv_id, "user", req.message,  # salva original, não comprimido
        input_tokens=response.input_tokens,
    )
    memory.add_message(
        conv_id, "assistant", response.content,
        model_used=response.model_id,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
    )

    return ChatResponse(
        content=response.content,
        model_id=response.model_id,
        provider=response.provider,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
        complexity=response.complexity.name if response.complexity else None,
        conversation_id=conv_id,
        compression_savings=compression_saved,
    )


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket para chat em tempo real."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            msg = data.get("message", "")
            conv_id = data.get("conversation_id")
            agent_name = data.get("agent_name", "main")

            if not msg:
                await websocket.send_json({"type": "error", "error": "mensagem vazia"})
                continue

            # Cria conversa se não existe
            if not conv_id:
                conv_id = memory.create_conversation(agent_name=agent_name)
                await websocket.send_json({
                    "type": "conversation_created",
                    "conversation_id": conv_id,
                })

            # Compressão
            compressed = default_compressor.compress(msg)
            effective_input = compressed.compressed if compressed.tokens_saved_estimate > 2 else msg

            if compressed.tokens_saved_estimate > 2:
                await websocket.send_json({
                    "type": "compression",
                    "saved": compressed.tokens_saved_estimate,
                    "percent": compressed.savings_percent,
                })

            # Classificação
            complexity, reason = classifier.classify_with_explanation(effective_input)
            await websocket.send_json({
                "type": "classification",
                "complexity": complexity.name,
                "reason": reason,
            })

            # Contexto
            context_messages = memory.get_context_for_llm(conv_id, token_budget=4000)
            agent_mem = get_agent_memory(agent_name)
            agent_context = agent_mem.get_context_for_llm(
                query=effective_input, token_budget=1500,
            )
            agent_info = AgentRegistry.get(agent_name) or {}
            system_prompt = (
                agent_info.get("system_prompt")
                or "Você é um assistente prestativo. Responda em português."
            )
            if agent_context:
                system_prompt += f"\n\n{agent_context}"

            # Chama LLM
            llm_req = LLMRequest(
                prompt=effective_input,
                system=system_prompt,
                messages=context_messages,
                conversation_id=conv_id,
            )
            response = await asyncio.get_event_loop().run_in_executor(
                None, router.route, llm_req
            )

            if response.error:
                await websocket.send_json({
                    "type": "error",
                    "error": response.error,
                })
                continue

            # Salva mensagens
            memory.add_message(conv_id, "user", msg, input_tokens=response.input_tokens)
            memory.add_message(
                conv_id, "assistant", response.content,
                model_used=response.model_id,
                output_tokens=response.output_tokens,
                cost_usd=response.cost_usd,
            )

            # Envia resposta
            await websocket.send_json({
                "type": "response",
                "content": response.content,
                "model_id": response.model_id,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
                "conversation_id": conv_id,
            })
    except WebSocketDisconnect:
        pass


# ==========================================================================
# ROTAS: CONVERSAS E MENSAGENS
# ==========================================================================

@app.get("/api/conversations")
def list_conversations(limit: int = 50, archived: bool = False):
    """Lista conversas."""
    rows = db.fetch_all(
        """
        SELECT * FROM conversations WHERE archived = ?
        ORDER BY updated_at DESC LIMIT ?
        """,
        (int(archived), limit),
    )
    return {"conversations": rows}


@app.get("/api/conversations/{conv_id}/messages")
def get_messages(conv_id: int):
    """Pega todas as mensagens de uma conversa."""
    rows = db.fetch_all(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
        (conv_id,),
    )
    return {"messages": rows}


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int):
    """Arquiva uma conversa."""
    db.execute("UPDATE conversations SET archived = 1 WHERE id = ?", (conv_id,))
    return {"status": "archived"}


# ==========================================================================
# ROTAS: AGENTES
# ==========================================================================

@app.get("/api/agents")
def list_agents():
    """Lista todos os agentes."""
    return {"agents": AgentRegistry.list_all()}


@app.get("/api/agents/{name}")
def get_agent(name: str):
    """Detalhes de um agente."""
    ag = AgentRegistry.get(name)
    if not ag:
        raise HTTPException(404, f"Agente '{name}' não encontrado")

    mem = get_agent_memory(name)
    return {
        "agent": ag,
        "memory_stats": mem.stats(),
        "subagents": AgentRegistry.list_subagents(name),
    }


@app.post("/api/agents")
def create_agent(req: CreateAgentRequest):
    """Cria um novo sub-agente."""
    if AgentRegistry.get(req.name):
        raise HTTPException(400, f"Agente '{req.name}' já existe")

    if not AgentRegistry.get(req.parent_agent):
        raise HTTPException(400, f"Agente pai '{req.parent_agent}' não existe")

    system_prompt = req.system_prompt or (
        f"Você é o sub-agente '{req.name}' com a função: {req.role}. "
        "Responda de forma direta e objetiva em português."
    )

    AgentRegistry.register(
        name=req.name,
        role=req.role,
        parent_agent=req.parent_agent,
        system_prompt=system_prompt,
        preferred_model=req.preferred_model,
    )
    return {"status": "created", "name": req.name}


@app.get("/api/agents/{name}/memory")
def get_agent_memory_data(name: str):
    """Retorna toda a memória de um agente."""
    if not AgentRegistry.get(name):
        raise HTTPException(404, f"Agente '{name}' não encontrado")

    rows = db.fetch_all(
        """
        SELECT * FROM agent_memory WHERE agent_name = ?
        ORDER BY level, relevance DESC
        """,
        (name,),
    )

    grouped = {"core": [], "learned": [], "episodic": []}
    for row in rows:
        grouped.setdefault(row["level"], []).append(row)

    return grouped


# ==========================================================================
# ROTAS: MEMÓRIA COMPARTILHADA
# ==========================================================================

@app.get("/api/shared-memory/channels")
def list_channels():
    """Lista todos os canais de memória compartilhada."""
    return {"channels": shared_bus.list_namespaces()}


@app.get("/api/shared-memory/{namespace}")
def get_channel_memories(namespace: str, agent: Optional[str] = None):
    """Pega memórias de um canal específico."""
    rows = db.fetch_all(
        "SELECT * FROM shared_memory WHERE namespace = ? ORDER BY created_at DESC",
        (namespace,),
    )
    return {"namespace": namespace, "entries": rows}


@app.post("/api/shared-memory")
def share_memory(req: ShareMemoryRequest):
    """Publica memória compartilhada."""
    shared_bus.publish(
        namespace=req.namespace,
        key=req.key,
        content=req.content,
        source_agent=req.source_agent,
        target_agents=req.target_agents,
        ttl_hours=req.ttl_hours,
    )
    return {"status": "published"}


# ==========================================================================
# ROTAS: VAULT (SEGUNDO CÉREBRO)
# ==========================================================================

@app.get("/api/vault/status")
def vault_status():
    """Estatísticas do vault."""
    from backend.memory.vault import VAULT_STRUCTURE
    result = {}
    for label, folder in VAULT_STRUCTURE.items():
        path = VAULT_DIR / folder
        if path.exists():
            files = list(path.rglob("*.md"))
            result[label] = {
                "path": folder,
                "count": len(files),
                "size_kb": sum(f.stat().st_size for f in files if f.is_file()) // 1024,
            }
    return result


@app.post("/api/vault/notes")
def save_note(req: SaveNoteRequest):
    """Salva uma nota no vault."""
    if req.layer == "wiki":
        filepath = vault.save_wiki(
            title=req.title, content=req.content,
            category=req.category, tags=req.tags,
        )
    elif req.layer == "raw":
        filepath = vault.save_raw(title=req.title, content=req.content)
    else:
        filepath = vault.save_output(title=req.title, content=req.content)

    return {
        "status": "saved",
        "path": str(filepath.relative_to(VAULT_DIR)),
    }


@app.get("/api/vault/search")
def vault_search(q: str, layer: Optional[str] = None, limit: int = 10):
    """Busca notas no vault."""
    return {"results": vault.search(q, layer=layer, limit=limit)}


@app.get("/api/vault/graph")
def vault_graph():
    """Retorna o grafo de conhecimento (para D3/Recharts)."""
    graph = vault.build_graph()

    # Converte para formato de grafo visual (nodes + edges)
    nodes = []
    edges = []
    seen = set()

    for source, links in graph.items():
        if source not in seen:
            nodes.append({"id": source, "label": source})
            seen.add(source)
        for target in links:
            if target not in seen:
                nodes.append({"id": target, "label": target})
                seen.add(target)
            edges.append({"source": source, "target": target})

    return {"nodes": nodes, "edges": edges}


@app.get("/api/vault/entities")
def vault_entities():
    """Lista todas as entidades do vault."""
    return vault.list_entities()


# ==========================================================================
# ROTAS: ORÇAMENTO E USO
# ==========================================================================

@app.get("/api/usage/budget")
def get_budget():
    """Gastos do mês atual."""
    spend = get_monthly_spend()
    return {
        **spend,
        "limit_usd": APP_CONFIG.monthly_budget_usd,
    }


@app.get("/api/usage/by-model")
def usage_by_model(days: int = 30):
    """Uso agrupado por modelo nos últimos N dias."""
    rows = db.fetch_all(
        """
        SELECT model_id, provider,
               COUNT(*) as calls,
               SUM(input_tokens) as input_tokens,
               SUM(output_tokens) as output_tokens,
               SUM(cost_usd) as total_cost
        FROM usage_log
        WHERE timestamp >= datetime('now', ? || ' days')
          AND success = 1
        GROUP BY model_id ORDER BY total_cost DESC
        """,
        (f"-{days}",),
    )
    return {"usage": rows, "days": days}


@app.get("/api/usage/daily")
def usage_daily(days: int = 30):
    """Uso diário (série temporal para gráfico)."""
    rows = db.fetch_all(
        """
        SELECT DATE(timestamp) as day,
               COUNT(*) as calls,
               SUM(cost_usd) as cost,
               SUM(input_tokens + output_tokens) as tokens
        FROM usage_log
        WHERE timestamp >= datetime('now', ? || ' days')
          AND success = 1
        GROUP BY DATE(timestamp) ORDER BY day
        """,
        (f"-{days}",),
    )
    return {"daily": rows, "days": days}


# ==========================================================================
# WHATSAPP — IMPORTA ROTAS DO MÓDULO ESPECÍFICO
# ==========================================================================

try:
    from backend.channels.whatsapp.webhook import router as whatsapp_router
    app.include_router(whatsapp_router, prefix="/api/whatsapp", tags=["whatsapp"])
except ImportError:
    pass  # Módulo WhatsApp opcional


# ==========================================================================
# ENTRY POINT
# ==========================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
