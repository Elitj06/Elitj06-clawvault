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
import json as _json
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

# Carrega .env antes de tudo
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from backend.core.config import MODELS_CATALOG, APP_CONFIG, API_KEYS, VAULT_DIR, TaskComplexity
from backend.core.database import db, get_monthly_spend
from backend.llm.router import router, LLMRequest
from backend.llm.classifier import classifier
from backend.memory.manager import memory
from backend.memory.vault import vault
# Import tools — auto-registers in registry via __init_subclass__
import backend.tools.builtins  # noqa: F401
from backend.tools.registry import registry as tool_registry
from backend.memory.multi_agent import (
    AgentRegistry, get_agent_memory, shared_bus,
    ensure_multi_agent_schema,
)
from backend.compression import default_compressor
from backend.observability import metrics
from backend.slash_commands import (
    is_slash_command,
    execute_slash_command,
    list_commands,
)
# P1 - Fact extractor
from backend.fact_extractor import (
    extractor as fact_extractor,
    get_facts_for_context,
    format_facts_for_prompt,
    deprecate_fact,
    deprecate_facts_about,
    stats as facts_stats,
)
from backend.background import worker as bg_worker, should_extract_facts
# P2 - Semantic search
from backend.embeddings import embed, health_check as embeddings_health
from backend.search import (
    semantic_search,
    hybrid_search,
    cache_lookup,
    cache_store,
    index_note,
    reindex_all,
    index_stats,
)

# P1 — Fact extraction
try:
    from backend.fact_extractor import (
        FactExtractor, get_facts_for_context, format_facts_for_prompt,
        ensure_facts_schema, stats as facts_stats, deprecate_fact,
    )
    from backend.background import BackgroundWorker, should_extract_facts
    bg_worker = BackgroundWorker()
    _P1_ENABLED = True
except ImportError:
    _P1_ENABLED = False
    bg_worker = None

# P2 — Semantic search / embeddings
try:
    from backend.search import (
        semantic_search, hybrid_search, cache_lookup, cache_store,
        index_note, reindex_all, index_stats,
    )
    from backend.embeddings import health_check as embeddings_health
    _P2_ENABLED = True
except ImportError:
    _P2_ENABLED = False


# ==========================================================================
# LIFECYCLE
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialização do servidor."""
    # Garante que o banco está inicializado
    db.initialize()
    ensure_multi_agent_schema()

    # P1 — Facts schema + background worker
    if _P1_ENABLED:
        ensure_facts_schema()
        bg_worker.start()

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
    if _P1_ENABLED and bg_worker:
        bg_worker.stop()
    print("👋 Servidor encerrado.")


app = FastAPI(
    title="ClawVault API",
    version=APP_CONFIG.version,
    description="Sistema de agentes multi-LLM com memória persistente",
    lifespan=lifespan,
)

# CORS — permite acesso do frontend local e externo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
                 "bigmodel", "groq", "moonshot", "minimax", "alibaba", "openrouter"):
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
    # === SLASH COMMAND INTERCEPTION (P7) ===
    if is_slash_command(req.message):
        result = execute_slash_command(req.message)
        if result is not None:
            conv_id = req.conversation_id or memory.create_conversation(
                agent_name=req.agent_name
            )
            memory.add_message(conv_id, "user", req.message)
            memory.add_message(
                conv_id, "assistant", result.message,
                model_used="slash-command-local",
            )
            return ChatResponse(
                content=result.message,
                model_id="slash-command",
                provider="local",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                complexity="TRIVIAL",
                conversation_id=conv_id,
                compression_savings=0,
            )

    # === SEMANTIC CACHE LOOKUP (P2) ===
    # Antes de chamar LLM, procura resposta cacheada para pergunta similar
    if _P2_ENABLED:
        cached = cache_lookup(req.message)
        if cached:
            conv_id = req.conversation_id or memory.create_conversation(
                agent_name=req.agent_name
            )
            memory.add_message(conv_id, "user", req.message)
            memory.add_message(
                conv_id, "assistant", cached["response"],
                model_used=cached["model_id"] + "-cached",
            )
            return ChatResponse(
                content=cached["response"],
                model_id=cached["model_id"] + "-cached",
                provider="semantic-cache",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                complexity="CACHED",
                conversation_id=conv_id,
                compression_savings=0,
            )

    # === fluxo normal ===
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
    context_messages = memory.get_context_for_llm(conv_id, token_budget=1000)

    # Busca memória do agente
    agent_mem = get_agent_memory(req.agent_name)
    agent_context = agent_mem.get_context_for_llm(
        query=effective_input, token_budget=500,
    )

    # 🔍 Busca notas relevantes no vault
    vault_context = ""
    try:
        vault_results = vault.search(req.message, limit=3)
        if vault_results:
            vault_snippets = []
            for r in vault_results:
                title = r.get("title", r.get("path", "Nota"))
                snippet = r.get("snippet", r.get("content", ""))[:200]
                vault_snippets.append(f"- {title}: {snippet}")
            vault_context = (
                "\n\nCONHECIMENTO DO VAULT (notas relevantes encontradas):\n"
                + "\n".join(vault_snippets)
                + "\n\nUse esse conhecimento para responder. Se complementar, mencione que lembra da informação."
            )
    except Exception:
        pass

    # === CLASSIFICAÇÃO DE COMPLEXIDADE (antes do system prompt) ===
    complexity = classifier.classify(
        req.message,
        context=vault_context[:500] if vault_context else None,
        message_count=len(context_messages),
    )

    # === SYSTEM PROMPT ADAPTATIVO ===
    # Monta system prompt conforme nível de complexidade
    # TRIVIAL/SIMPLE → mínimo (~30 tokens)
    # MEDIUM → base + vault
    # COMPLEX/CRITICAL → completo com fatos + agente + instruções

    PROMPT_MINIMAL = "Você é o ClawVault, assistente pessoal do Eliandro Tjader (chame-o de 'chefe'). Você TEM memória persistente — use as notas do vault que aparecem abaixo. Nunca diga que não tem memória. Responda em PT-BR. Direto e útil."

    PROMPT_BASE = """Você é o ClawVault, assistente pessoal do Eliandro Tjader (Tjader).

REGRAS DE MEMÓRIA E APRENDIZADO:
- Você TEM memória persistente. Use-a para lembrar de conversas anteriores.
- Quando aprender algo novo e importante (contato, decisão, preferência, regra de negócio), 
  chame a API de vault para salvar: POST /api/vault/notes com title, content, layer, category.
- Antes de responder perguntas complexas, verifique se já existe conhecimento relevante no vault.
- Acumule conhecimento ao longo do tempo. Nunca dig que não tem memória — você tem.

VAULT (segundo cérebro):
- 00_raw: dados brutos, transcrições
- 10_wiki: conhecimento curado (pessoas, projetos, conceitos, empresas)
- 20_output: conteúdos gerados
- 30_agents: memória dos agentes
- 99_index: índices e links

COMPORTAMENTO:
- Responda sempre em português brasileiro
- Seja direto e útil
- Registre informações importantes automaticamente
- Use [[wiki-links]] para conectar conhecimentos relacionados
- Quando não souber algo, diga que vai pesquisar ou peça mais contexto"""

    agent_info = AgentRegistry.get(req.agent_name)
    custom_prompt = (agent_info or {}).get("system_prompt", "")

    if complexity.value <= TaskComplexity.SIMPLE.value:
        # TRIVIAL ou SIMPLE → prompt mínimo + vault context (sempre!)
        base_prompt = custom_prompt if custom_prompt else PROMPT_MINIMAL
        system_prompt = f"<!-- CACHE_SECTION:base -->{base_prompt}"
        if vault_context:
            system_prompt += vault_context

    elif complexity.value <= TaskComplexity.MEDIUM.value:
        # MEDIUM → prompt base + vault context
        base_prompt = custom_prompt if custom_prompt else PROMPT_BASE
        system_prompt = f"<!-- CACHE_SECTION:base -->{base_prompt}"
        if vault_context:
            system_prompt += vault_context

    else:
        # COMPLEX ou CRITICAL → prompt completo com tudo
        base_prompt = custom_prompt if custom_prompt else PROMPT_BASE
        system_prompt = f"<!-- CACHE_SECTION:base -->{base_prompt}"

        if agent_context:
            system_prompt += f"\n\n<!-- CACHE_SECTION:agent -->{agent_context}"

        # P1 — Injeta fatos extraídos
        facts_section = ""
        if _P1_ENABLED:
            try:
                facts = get_facts_for_context(query=req.message, limit=8)
                if facts:
                    facts_section = format_facts_for_prompt(facts)
            except Exception:
                pass
        if facts_section:
            system_prompt += f"\n\n<!-- CACHE_SECTION:memory -->{facts_section}"

        if vault_context:
            system_prompt += vault_context

    # Mount available tool schemas
    tools_schemas = tool_registry.schemas()

    # Chama o LLM (passa complexidade já classificada pra evitar reclassificação)
    llm_req = LLMRequest(
        prompt=effective_input,
        system=system_prompt,
        messages=context_messages,
        model_override=req.model_override,
        conversation_id=conv_id,
        complexity_hint=complexity,
        tools=tools_schemas,
        tool_choice="auto" if tools_schemas else None,
    )

    # === AGENTIC TOOL LOOP ===
    max_iterations = 5
    for iteration in range(max_iterations):
        response = router.route(llm_req)

        if response.error:
            raise HTTPException(status_code=500, detail=response.error)

        # No tool calls — done, return as before
        if not response.tool_calls:
            break

        # Execute tool calls and continue the loop
        import logging as _logging
        _logger = _logging.getLogger("clawvault.tools")
        _logger.info(f"[Agent Loop] Iteration {iteration + 1}: {len(response.tool_calls)} tool call(s)")

        # Append assistant message with tool_calls to messages
        loop_messages = list(llm_req.messages or [])
        if llm_req.system:
            loop_messages = [{"role": "system", "content": llm_req.system}] + loop_messages
        if iteration == 0 and llm_req.prompt:
            loop_messages.append({"role": "user", "content": llm_req.prompt})

        # Build assistant message with tool_calls
        assistant_tool_calls = []
        for tc in response.tool_calls:
            assistant_tool_calls.append({
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": _json.dumps(tc["arguments"], ensure_ascii=False)},
            })

        loop_messages.append({
            "role": "assistant",
            "content": response.content or None,
            "tool_calls": assistant_tool_calls,
        })

        # Execute each tool and add tool results
        for tc in response.tool_calls:
            result = tool_registry.dispatch(tc["name"], tc["arguments"])
            _logger.info(f"[Agent Loop] Tool {tc['name']} → {len(result)} chars")
            loop_messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        # Prepare next iteration — no system/prompt needed (already in messages)
        llm_req = LLMRequest(
            prompt=None,
            system=None,
            messages=loop_messages,
            model_override=req.model_override,
            conversation_id=conv_id,
            complexity_hint=complexity,
            tools=tools_schemas,
            tool_choice="auto" if tools_schemas else None,
        )
    else:
        # Max iterations reached — get one final response without tools
        response = router.route(LLMRequest(
            prompt=None,
            system=None,
            messages=llm_req.messages,
            model_override=req.model_override,
            conversation_id=conv_id,
            complexity_hint=complexity,
        ))
        if response.error:
            raise HTTPException(status_code=500, detail=response.error)

    # response now holds the final text response

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

    # P1 — Agenda extração de fatos em background
    if _P1_ENABLED and should_extract_facts(conv_id):
        bg_worker.enqueue_fact_extraction(conv_id)

    # 🧠 Auto-aprendizado: detecta e salva informações importantes no vault
    try:
        from backend.memory.auto_learn import auto_learner
        auto_learner.vault = vault
        findings = auto_learner.process_exchange(
            user_message=req.message,
            assistant_response=response.content,
            conversation_id=conv_id,
        )
        if findings:
            saved = auto_learner.save_findings(findings)
            if saved:
                import logging
                logging.info(f"[AutoLearn] Salvo {len(saved)} nota(s) no vault")
    except Exception as e:
        import logging
        logging.warning(f"[AutoLearn] Erro (não fatal): {e}")

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


# ==========================================================================
# STREAMING ENDPOINT (P4)
# ==========================================================================

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Versão streaming do /api/chat.
    Retorna eventos SSE com deltas de texto enquanto o LLM gera a resposta.
    """
    # === SLASH COMMAND INTERCEPTION (P7) ===
    if is_slash_command(req.message):
        result = execute_slash_command(req.message)
        if result is not None:
            conv_id = req.conversation_id or memory.create_conversation(
                agent_name=req.agent_name
            )
            memory.add_message(conv_id, "user", req.message)
            memory.add_message(
                conv_id, "assistant", result.message,
                model_used="slash-command-local",
            )

            async def slash_generator():
                yield _sse_event("meta", {
                    "conversation_id": conv_id,
                    "model": "slash-command",
                    "provider": "local",
                    "complexity": "TRIVIAL",
                })
                yield _sse_event("delta", {"text": result.message})
                yield _sse_event("done", {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cached_tokens": 0,
                    "cost_usd": 0.0,
                    "compression_savings": 0,
                    "is_command": True,
                    "command_data": result.data,
                })

            return StreamingResponse(
                slash_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    conv_id = req.conversation_id
    if not conv_id:
        conv_id = memory.create_conversation(agent_name=req.agent_name)

    effective_input = req.message
    compression_saved = 0
    if req.compress:
        result = default_compressor.compress(req.message)
        if result.tokens_saved_estimate > 2:
            effective_input = result.compressed
            compression_saved = result.tokens_saved_estimate

    context_messages = memory.get_context_for_llm(conv_id, token_budget=4000)
    agent_mem = get_agent_memory(req.agent_name)
    agent_context = agent_mem.get_context_for_llm(
        query=effective_input, token_budget=1500,
    )

    agent_info = AgentRegistry.get(req.agent_name)
    system_prompt = (
        (agent_info.get("system_prompt") if agent_info else "")
        or "Você é um assistente prestativo. Responda em português."
    )
    if agent_context:
        system_prompt += f"\n\n{agent_context}"

    async def event_generator():
        try:
            llm_req = LLMRequest(
                prompt=effective_input,
                system=system_prompt,
                messages=context_messages,
                model_override=req.model_override,
                conversation_id=conv_id,
            )

            # Tenta streaming real via route_stream
            if hasattr(router, 'route_stream'):
                import threading
                import queue as _queue

                q = _queue.Queue()
                full_content = []

                def _stream_thread():
                    try:
                        for chunk in router.route_stream(llm_req):
                            q.put(chunk)
                    except Exception as e:
                        q.put({"type": "error", "error": str(e)})
                    finally:
                        q.put(None)  # sentinel

                t = threading.Thread(target=_stream_thread, daemon=True)
                t.start()

                model_id = None
                provider = None
                usage_info = {}

                while True:
                    item = await asyncio.get_event_loop().run_in_executor(None, q.get)
                    if item is None:
                        break

                    if item["type"] == "delta":
                        full_content.append(item.get("text", ""))
                        yield _sse_event("delta", {"text": item.get("text", "")})
                    elif item["type"] == "done":
                        usage_info = item.get("usage", {})
                        model_id = item.get("model_id")
                        provider = item.get("provider")
                    elif item["type"] == "error":
                        yield _sse_event("error", {"error": item.get("error", "unknown")})
                        return

                # Emit meta after first deltas or use fallback
                if not model_id:
                    model_id = "unknown"

                yield _sse_event("meta", {
                    "conversation_id": conv_id,
                    "model": model_id,
                    "provider": provider or "unknown",
                })

                content_str = "".join(full_content)
                memory.add_message(conv_id, "user", req.message,
                                   input_tokens=usage_info.get("input_tokens", 0))
                memory.add_message(conv_id, "assistant", content_str,
                                   model_used=model_id,
                                   output_tokens=usage_info.get("output_tokens", 0),
                                   cost_usd=usage_info.get("cost_usd", 0))

                # P1 — background fact extraction
                if _P1_ENABLED and should_extract_facts(conv_id):
                    bg_worker.enqueue_fact_extraction(conv_id)

                yield _sse_event("done", {
                    **usage_info,
                    "compression_savings": compression_saved,
                })
                return

            # Fallback: fake streaming
            response = router.route(llm_req)

            if response.error:
                yield _sse_event("error", {"error": response.error})
                return

            yield _sse_event("meta", {
                "conversation_id": conv_id,
                "model": response.model_id,
                "provider": response.provider,
                "complexity": response.complexity.name if response.complexity else None,
            })

            content = response.content or ""
            chunk_size = 8
            words = content.split(" ")
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                yield _sse_event("delta", {"text": chunk})
                await asyncio.sleep(0.03)

            memory.add_message(
                conv_id, "user", req.message,
                input_tokens=response.input_tokens,
            )
            memory.add_message(
                conv_id, "assistant", response.content,
                model_used=response.model_id,
                output_tokens=response.output_tokens,
                cost_usd=response.cost_usd,
            )

            if _P1_ENABLED and should_extract_facts(conv_id):
                bg_worker.enqueue_fact_extraction(conv_id)

            yield _sse_event("done", {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cached_tokens": response.cached_tokens,
                "cost_usd": response.cost_usd,
                "compression_savings": compression_saved,
            })

        except Exception as e:
            yield _sse_event("error", {"error": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event_name: str, data: dict) -> str:
    """Formata um evento SSE."""
    return f"event: {event_name}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/commands")
def list_available_commands():
    """Lista todos os slash commands disponíveis (para autocomplete na UI)."""
    return {"commands": list_commands()}


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
            context_messages = memory.get_context_for_llm(conv_id, token_budget=1000)
            agent_mem = get_agent_memory(agent_name)
            agent_context = agent_mem.get_context_for_llm(
                query=effective_input, token_budget=500,
            )
            agent_info = AgentRegistry.get(agent_name) or {}
            system_prompt = (
                agent_info.get("system_prompt")
                or """Você é o ClawVault, assistente pessoal do Eliandro Tjader (Tjader).
Você TEM memória persistente. Quando aprender algo importante, salve no vault via POST /api/vault/notes.
Acumule conhecimento. Nunca dig que não tem memória. Responda em português brasileiro. Seja direto e útil."""
            )
            # P8 — cache markers
            system_prompt = f"<!-- CACHE_SECTION:base -->{system_prompt}"
            if agent_context:
                system_prompt += f"\n\n<!-- CACHE_SECTION:agent -->{agent_context}"
            # P1 facts injection
            if _P1_ENABLED:
                try:
                    facts = get_facts_for_context(query=msg, limit=8)
                    if facts:
                        system_prompt += f"\n\n<!-- CACHE_SECTION:memory -->{format_facts_for_prompt(facts)}"
                except Exception:
                    pass

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


@app.get("/api/vault/notes/{note_path:path}")
def read_note(note_path: str):
    """Lê o conteúdo completo de uma nota do vault."""
    full_path = VAULT_DIR / note_path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"Nota não encontrada: {note_path}")
    # Security: ensure path doesn't escape vault
    try:
        full_path.resolve().relative_to(VAULT_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Acesso negado")
    content = full_path.read_text(encoding="utf-8")
    return {"path": note_path, "content": content, "size": len(content)}


@app.delete("/api/vault/notes/{note_path:path}")
def delete_note(note_path: str):
    """Remove uma nota do vault."""
    full_path = VAULT_DIR / note_path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"Nota não encontrada: {note_path}")
    try:
        full_path.resolve().relative_to(VAULT_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Acesso negado")
    full_path.unlink()
    return {"status": "deleted", "path": note_path}


@app.get("/api/vault/graph")
def vault_graph():
    """Retorna o grafo de conhecimento (para D3/Recharts)."""
    import glob as _glob

    # Scan all .md files and build nodes with proper metadata
    nodes = []
    node_map = {}
    seen_ids = set()

    for filepath in sorted(_glob.glob(str(VAULT_DIR / "**" / "*.md"), recursive=True)):
        rel = os.path.relpath(filepath, str(VAULT_DIR))
        stem = Path(filepath).stem

        # Extract category from path
        parts = rel.split(os.sep)
        if len(parts) >= 3:
            category = parts[1]  # eventos, projetos, conceitos, pessoas, drafts
        elif len(parts) >= 2:
            category = parts[0]  # 10_wiki, 00_raw, 99_index
        else:
            category = "other"

        # Human-friendly label
        label = stem
        if label.startswith("openclaw-"):
            label = label.replace("openclaw-", "")
        elif label.startswith("2026-"):
            # Extract meaningful part after the date prefix
            match = __import__("re").match(r"\d{4}-\d{2}-\d{2}[_-](.+)", label)
            if match:
                label = match.group(1).replace("-", " ")[:40]
        elif label.startswith("openclaw-"):
            label = label.replace("openclaw-", "")

        node_id = stem
        if node_id not in seen_ids:
            node = {
                "id": node_id,
                "label": label,
                "path": rel,
                "category": category,
            }
            nodes.append(node)
            node_map[node_id] = node
            seen_ids.add(node_id)

    # Build edges from vault graph (entity links)
    graph = vault.build_graph()
    edges = []
    for source, links in graph.items():
        for target in links:
            edges.append({"source": source, "target": target})

    return {"nodes": nodes, "edges": edges}


@app.get("/api/vault/entities")
def vault_entities():
    """Lista todas as entidades do vault."""
    return vault.list_entities()


# ==========================================================================
# ROTAS: OBSERVABILITY (P3)
# ==========================================================================

@app.get("/api/observability/overview")
def observability_overview(days: int = 7):
    """Visão geral das métricas dos últimos N dias."""
    return metrics.overview(days=days)


@app.get("/api/observability/by-model")
def observability_by_model(days: int = 7):
    """Quebra de uso/custo por modelo."""
    return {"models": metrics.by_model(days=days)}


@app.get("/api/observability/by-agent")
def observability_by_agent(days: int = 7):
    """Quebra de uso/custo por agente."""
    return {"agents": metrics.by_agent(days=days)}


@app.get("/api/observability/cache")
def observability_cache(days: int = 7):
    """Métricas detalhadas de prompt caching."""
    return metrics.cache_metrics(days=days)


@app.get("/api/observability/timeline")
def observability_timeline(days: int = 30, granularity: str = "day"):
    """Série temporal de uso. granularity = 'day' ou 'hour'."""
    return {"timeline": metrics.timeline(days=days, granularity=granularity)}


@app.get("/api/observability/top-conversations")
def observability_top_conversations(limit: int = 10):
    """Conversas mais caras do último mês."""
    return {"conversations": metrics.top_conversations(limit=limit)}


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
# ROTAS: P1 — FACTS (Extração de Fatos)
# ==========================================================================

@app.get("/api/facts")
def list_facts(entity: Optional[str] = None, limit: int = 50):
    """Lista fatos extraídos."""
    if not _P1_ENABLED:
        raise HTTPException(501, "P1 (facts) não disponível")
    if entity:
        rows = db.fetch_all(
            "SELECT * FROM facts WHERE entity = ? ORDER BY created_at DESC LIMIT ?",
            (entity, limit),
        )
    else:
        rows = db.fetch_all(
            "SELECT * FROM facts ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    return {"facts": rows}


@app.get("/api/facts/stats")
def get_facts_stats():
    """Estatísticas de fatos."""
    if not _P1_ENABLED:
        raise HTTPException(501, "P1 (facts) não disponível")
    return facts_stats()


@app.post("/api/facts/extract/{conv_id}")
def trigger_fact_extraction(conv_id: int):
    """Dispara extração de fatos para uma conversa."""
    if not _P1_ENABLED:
        raise HTTPException(501, "P1 (facts) não disponível")
    bg_worker.enqueue_fact_extraction(conv_id)
    return {"status": "enqueued", "conversation_id": conv_id}


@app.delete("/api/facts/{fact_id}")
def delete_fact(fact_id: int):
    """Deprecate um fato."""
    if not _P1_ENABLED:
        raise HTTPException(501, "P1 (facts) não disponível")
    ok = deprecate_fact(fact_id)
    if not ok:
        raise HTTPException(404, "Fato não encontrado")
    return {"status": "deprecated", "fact_id": fact_id}


@app.get("/api/worker/stats")
def get_worker_stats():
    """Estatísticas do background worker."""
    if not _P1_ENABLED:
        raise HTTPException(501, "Worker não disponível")
    return bg_worker.stats()


# ==========================================================================
# ROTAS: P2 — SEMANTIC SEARCH / EMBEDDINGS
# ==========================================================================

@app.post("/api/embeddings/reindex")
def trigger_reindex():
    """Dispara reindexação completa do vault."""
    if not _P2_ENABLED:
        raise HTTPException(501, "P2 (embeddings) não disponível")
    result = reindex_all()
    return result


@app.get("/api/embeddings/stats")
def get_embeddings_stats():
    """Estatísticas de embeddings."""
    if not _P2_ENABLED:
        raise HTTPException(501, "P2 (embeddings) não disponível")
    return index_stats()


@app.get("/api/embeddings/health")
def get_embeddings_health():
    """Health check dos embeddings."""
    if not _P2_ENABLED:
        raise HTTPException(501, "P2 (embeddings) não disponível")
    return embeddings_health()


@app.delete("/api/cache/clear")
def clear_semantic_cache(older_than_days: Optional[int] = None):
    """Limpa cache semântico."""
    if not _P2_ENABLED:
        raise HTTPException(501, "P2 (cache) não disponível")
    from backend.search import cache_clear
    removed = cache_clear(older_than_days)
    return {"removed": removed}


# Modifica /api/vault/search para aceitar mode
_original_vault_search = vault_search

@app.get("/api/vault/search")  # type: ignore[misc]
def vault_search_enhanced(q: str, layer: Optional[str] = None, limit: int = 10, mode: str = "keyword"):
    """Busca notas no vault — suporta keyword, semantic e hybrid."""
    if mode == "keyword" or not _P2_ENABLED:
        return {"results": vault.search(q, layer=layer, limit=limit)}
    elif mode == "semantic":
        results = semantic_search(q, limit=limit)
        return {"results": results, "mode": "semantic"}
    elif mode == "hybrid":
        results = hybrid_search(q, limit=limit)
        return {"results": results, "mode": "hybrid"}
    else:
        raise HTTPException(400, f"Modo inválido: {mode}. Use: keyword, semantic, hybrid")


# ==========================================================================
# WHATSAPP — IMPORTA ROTAS DO MÓDULO ESPECÍFICO
# ==========================================================================

try:
    from backend.channels.whatsapp.webhook import router as whatsapp_router
    app.include_router(whatsapp_router, prefix="/api/whatsapp", tags=["whatsapp"])
except ImportError:
    pass  # Módulo WhatsApp opcional

# Bridge OpenClaw ↔ ClawVault
try:
    from backend.api.bridge import bridge_router
    app.include_router(bridge_router)
except ImportError:
    pass  # Bridge opcional


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
