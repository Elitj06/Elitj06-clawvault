# ClawVault — API Reference

> Documentação completa dos endpoints REST do ClawVault.
> Base URL: `http://localhost:8000`
> Docs interativas: `http://localhost:8000/docs`

---

## Índice

- [Status e Configuração](#status-e-configuração)
- [Chat](#chat)
- [Streaming Chat](#streaming-chat-sse)
- [WebSocket Chat](#websocket-chat)
- [Transcrição de Áudio](#transcrição-de-áudio)
- [Slash Commands](#slash-commands)
- [Conversas](#conversas)
- [Agentes](#agentes)
- [Memória Compartilhada](#memória-compartilhada)
- [Vault](#vault)
- [Fatos Extraídos](#fatos-extraídos)
- [Uso e Orçamento](#uso-e-orçamento)
- [Observabilidade](#observabilidade)
- [Embeddings e Busca Semântica](#embeddings-e-busca-semântica)
- [Bridge OpenClaw](#bridge-openclaw)
- [WhatsApp](#whatsapp)
- [Modelos Pydantic](#modelos-pydantic)
- [Códigos de Erro](#códigos-de-erro)

---

## Status e Configuração

### `GET /`

Health check.

**Response:**
```json
{
  "status": "ok",
  "service": "ClawVault",
  "version": "0.1.0",
  "timestamp": "2026-04-29T10:00:00"
}
```

---

### `GET /api/status`

Status geral do sistema — providers configurados, orçamento, estatísticas.

**Response:**
```json
{
  "version": "0.1.0",
  "providers": {
    "anthropic": true,
    "openai": false,
    "google": true,
    "zai": true,
    "groq": true,
    "deepseek": false,
    "openrouter": true,
    "bigmodel": true,
    "moonshot": false,
    "minimax": false,
    "alibaba": false
  },
  "budget": {
    "spent_usd": 1.23,
    "limit_usd": 50.0,
    "percent_used": 2.46
  },
  "stats": {
    "conversations": 42,
    "messages": 350,
    "agents": 3
  }
}
```

---

### `GET /api/models`

Lista todos os modelos do catálogo.

**Query Params:**

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `available_only` | bool | `false` | Filtrar só modelos com API key configurada |

**Response:**
```json
{
  "models": [
    {
      "id": "glm-5.1",
      "provider": "zai",
      "tier": "premium",
      "context_window": 200000,
      "cost_input": 1.0,
      "cost_output": 3.5,
      "supports_vision": false,
      "description": "GLM-5.1 — flagship da Z.ai",
      "available": true
    }
  ],
  "total": 52
}
```

---

## Chat

### `POST /api/chat`

Endpoint principal de chat. Envia uma mensagem e recebe resposta síncrona.

**Request Body (`ChatRequest`):**

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `message` | string | **obrigatório** | Mensagem do usuário |
| `conversation_id` | int? | `null` | ID da conversa existente (null = cria nova) |
| `agent_name` | string | `"main"` | Nome do agente |
| `model_override` | string? | `null` | Forçar um modelo específico (ex: `"claude-sonnet-4-6"`) |
| `compress` | bool | `true` | Aplicar compressão de prompt |

**Fluxo interno:**
1. Verifica se é slash command → executa localmente
2. Verifica cache semântico → retorna resposta cacheada se similar
3. Cria ou usa conversa existente
4. Comprime prompt (se habilitado)
5. Busca contexto (mensagens + memória do agente + vault)
6. Classifica complexidade (TRIVIAL→CRITICAL)
7. Monta system prompt adaptativo
8. Loop agentic com function calling (máx 5 iterações)
9. Salva mensagens + dispara extração de fatos em background

**Response (`ChatResponse`):**
```json
{
  "content": "Resposta do assistente...",
  "model_id": "glm-5.1",
  "provider": "zai",
  "input_tokens": 150,
  "output_tokens": 80,
  "cost_usd": 0.00043,
  "complexity": "SIMPLE",
  "conversation_id": 42,
  "compression_savings": 12
}
```

**Erros:**

| Status | Descrição |
|---|---|
| `500` | Modelo falhou (todos os fallbacks esgotados) |

---

## Streaming Chat (SSE)

### `POST /api/chat/stream`

Versão streaming do `/api/chat`. Retorna Server-Sent Events com deltas de texto.

**Request:** Mesmo `ChatRequest` do endpoint síncrono.

**Response:** `text/event-stream`

Eventos emitidos (em ordem):

```
event: meta
data: {"conversation_id": 42, "model": "glm-5.1", "provider": "zai", "complexity": "MEDIUM"}

event: delta
data: {"text": "Olá!"}

event: delta
data: {"text": " Como posso"}

event: done
data: {"input_tokens": 150, "output_tokens": 80, "cached_tokens": 0, "cost_usd": 0.00043, "compression_savings": 0}
```

Tipos de evento:

| Evento | Descrição |
|---|---|
| `meta` | Metadados da conversa e modelo selecionado |
| `delta` | Chunk de texto da resposta |
| `done` | Finalização com métricas de uso |
| `error` | Erro durante processamento |

---

## WebSocket Chat

### `WS /ws/chat`

WebSocket para chat em tempo real bidirecional.

**Envio (cliente → servidor):**
```json
{
  "message": "olá",
  "conversation_id": null,
  "agent_name": "main"
}
```

**Recebimento (servidor → cliente) — tipos de mensagem:**

| Tipo | Descrição |
|---|---|
| `conversation_created` | Nova conversa criada (com `conversation_id`) |
| `compression` | Compressão aplicada (`saved`, `percent`) |
| `classification` | Complexidade classificada (`complexity`, `reason`) |
| `response` | Resposta final (`content`, `model_id`, `cost_usd`, etc.) |
| `error` | Erro |

---

## Transcrição de Áudio

### `POST /api/transcribe`

Transcreve áudio usando Deepgram nova-3 (PT-BR).

**Request Body (`TranscribeRequest`):**

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `audio_data` | string | **obrigatório** | Áudio codificado em base64 |
| `mime_type` | string | `"audio/webm"` | MIME type do áudio |

**Response:**
```json
{
  "text": "Transcrição do áudio em português",
  "confidence": 0.95,
  "duration": 5.2
}
```

**Erros:**

| Status | Descrição |
|---|---|
| `500` | Falha na transcrição (API key não configurada ou erro Deepgram) |

---

## Slash Commands

### `GET /api/commands`

Lista todos os slash commands disponíveis (para autocomplete na UI).

**Response:**
```json
{
  "commands": [
    {"name": "/help", "description": "Lista comandos"},
    {"name": "/vault", "description": "Buscar no vault"},
    {"name": "/reset", "description": "Limpar conversa"}
  ]
}
```

---

## Conversas

### `GET /api/conversations`

Lista conversas.

**Query Params:**

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `limit` | int | `50` | Máximo de conversas |
| `archived` | bool | `false` | Incluir arquivadas |

**Response:**
```json
{
  "conversations": [
    {
      "id": 1,
      "agent_name": "main",
      "archived": false,
      "created_at": "2026-04-29T10:00:00",
      "updated_at": "2026-04-29T10:05:00"
    }
  ]
}
```

---

### `GET /api/conversations/{conv_id}/messages`

Retorna todas as mensagens de uma conversa.

**Path Params:**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `conv_id` | int | ID da conversa |

**Response:**
```json
{
  "messages": [
    {
      "id": 1,
      "conversation_id": 42,
      "role": "user",
      "content": "olá",
      "model_used": null,
      "input_tokens": 5,
      "output_tokens": null,
      "cost_usd": null,
      "created_at": "2026-04-29T10:00:00"
    },
    {
      "id": 2,
      "conversation_id": 42,
      "role": "assistant",
      "content": "Olá! Como posso ajudar?",
      "model_used": "glm-5.1",
      "input_tokens": null,
      "output_tokens": 8,
      "cost_usd": 0.00003,
      "created_at": "2026-04-29T10:00:01"
    }
  ]
}
```

---

### `DELETE /api/conversations/{conv_id}`

Arquiva uma conversa (soft delete).

**Response:**
```json
{"status": "archived"}
```

---

## Agentes

### `GET /api/agents`

Lista todos os agentes registrados.

**Response:**
```json
{
  "agents": [
    {
      "name": "main",
      "role": "Assistente pessoal principal",
      "is_main": true,
      "parent_agent": null,
      "preferred_model": null,
      "system_prompt": "...",
      "created_at": "2026-04-26T00:00:00"
    }
  ]
}
```

---

### `GET /api/agents/{name}`

Detalhes de um agente específico.

**Path Params:**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `name` | string | Nome do agente |

**Response:**
```json
{
  "agent": { "...": "..." },
  "memory_stats": {
    "core": 5,
    "learned": 12,
    "episodic": 30
  },
  "subagents": ["research", "coder"]
}
```

**Erros:**

| Status | Descrição |
|---|---|
| `404` | Agente não encontrado |

---

### `POST /api/agents`

Cria um novo sub-agente.

**Request Body (`CreateAgentRequest`):**

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `name` | string | **obrigatório** | Nome único do agente |
| `role` | string | **obrigatório** | Descrição da função |
| `parent_agent` | string | `"main"` | Agente pai |
| `preferred_model` | string? | `null` | Modelo preferido |
| `system_prompt` | string? | auto | Prompt de sistema customizado |

**Response:**
```json
{"status": "created", "name": "research"}
```

**Erros:**

| Status | Descrição |
|---|---|
| `400` | Agente já existe ou agente pai não encontrado |

---

### `GET /api/agents/{name}/memory`

Retorna toda a memória de um agente, agrupada por nível.

**Path Params:**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `name` | string | Nome do agente |

**Response:**
```json
{
  "core": [
    {"id": 1, "content": "O chefe se chama Eliandro", "relevance": 1.0}
  ],
  "learned": [
    {"id": 2, "content": "Prefere respostas em PT-BR", "relevance": 0.8}
  ],
  "episodic": [
    {"id": 3, "content": "Conversa sobre projeto X", "relevance": 0.5}
  ]
}
```

---

## Memória Compartilhada

### `GET /api/shared-memory/channels`

Lista todos os canais (namespaces) de memória compartilhada.

**Response:**
```json
{
  "channels": ["decisions", "contacts", "projects"]
}
```

---

### `GET /api/shared-memory/{namespace}`

Pega memórias de um canal específico.

**Path Params:**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `namespace` | string | Nome do canal |

**Response:**
```json
{
  "namespace": "decisions",
  "entries": [
    {
      "id": 1,
      "key": "stack-choice",
      "content": "Decidimos usar FastAPI",
      "source_agent": "main",
      "target_agents": null,
      "created_at": "2026-04-26T10:00:00"
    }
  ]
}
```

---

### `POST /api/shared-memory`

Publica memória no barramento compartilhado.

**Request Body (`ShareMemoryRequest`):**

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `namespace` | string | **obrigatório** | Canal de publicação |
| `key` | string | **obrigatório** | Chave identificadora |
| `content` | string | **obrigatório** | Conteúdo da memória |
| `source_agent` | string | `"main"` | Agente que publicou |
| `target_agents` | list? | `null` | Agentes destino (null = todos) |
| `ttl_hours` | int? | `null` | TTL em horas (null = permanente) |

**Response:**
```json
{"status": "published"}
```

---

## Vault

### `GET /api/vault/status`

Estatísticas do vault (contagem e tamanho por camada).

**Response:**
```json
{
  "raw": {"path": "00_raw", "count": 5, "size_kb": 12},
  "wiki": {"path": "10_wiki", "count": 25, "size_kb": 120},
  "output": {"path": "20_output", "count": 3, "size_kb": 8}
}
```

---

### `POST /api/vault/notes`

Salva uma nota no vault.

**Request Body (`SaveNoteRequest`):**

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `title` | string | **obrigatório** | Título da nota |
| `content` | string | **obrigatório** | Conteúdo em markdown |
| `layer` | string | `"wiki"` | Camada: `"raw"`, `"wiki"`, `"output"` |
| `category` | string | `"conceitos"` | Categoria (dentro da camada wiki) |
| `tags` | list | `[]` | Tags |

**Response:**
```json
{
  "status": "saved",
  "path": "10_wiki/conceitos/minha-nota.md"
}
```

---

### `GET /api/vault/search`

Busca notas no vault — suporta keyword, semantic e hybrid.

**Query Params:**

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `q` | string | **obrigatório** | Query de busca |
| `layer` | string? | `null` | Filtrar por camada |
| `limit` | int | `10` | Máximo de resultados |
| `mode` | string | `"keyword"` | Modo: `"keyword"`, `"semantic"`, `"hybrid"` |

**Response:**
```json
{
  "results": [
    {
      "title": "OpenClaw Memory",
      "path": "10_wiki/conceitos/openclaw-memory-geral.md",
      "snippet": "Conteúdo relevante encontrado...",
      "content": "..."
    }
  ],
  "mode": "hybrid"
}
```

> **Nota:** Modos `semantic` e `hybrid` requerem embeddings habilitados (Ollama ou OpenAI).

---

### `GET /api/vault/notes/{note_path}`

Lê o conteúdo completo de uma nota do vault.

**Path Params:**

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `note_path` | string | Caminho relativo da nota (ex: `10_wiki/conceitos/nota.md`) |

**Response:**
```json
{
  "path": "10_wiki/conceitos/nota.md",
  "content": "# Minha Nota\n\nConteúdo completo...",
  "size": 256
}
```

**Erros:**

| Status | Descrição |
|---|---|
| `404` | Nota não encontrada |
| `403` | Path traversal detectado |

---

### `DELETE /api/vault/notes/{note_path}`

Remove uma nota do vault.

**Response:**
```json
{"status": "deleted", "path": "10_wiki/conceitos/nota.md"}
```

**Erros:**

| Status | Descrição |
|---|---|
| `404` | Nota não encontrada |
| `403` | Path traversal detectado |

---

### `GET /api/vault/graph`

Retorna o grafo de conhecimento (nodes + edges) para visualização (D3/Recharts).

**Response:**
```json
{
  "nodes": [
    {"id": "openclaw-memory-geral", "label": "OpenClaw Memory", "path": "10_wiki/conceitos/...", "category": "conceitos"}
  ],
  "edges": [
    {"source": "openclaw-memory-geral", "target": "fitflow-suite-state"}
  ]
}
```

> Nota: Limitado a ~25 nodes. Eventos diários antigos são consolidados.

---

### `GET /api/vault/entities`

Lista todas as entidades detectadas no vault.

**Response:**
```json
["Eliandro", "FitFlow", "OpenClaw", "ClawVault"]
```

---

## Fatos Extraídos

### `GET /api/facts`

Lista fatos extraídos automaticamente.

**Query Params:**

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `entity` | string? | `null` | Filtrar por entidade |
| `limit` | int | `50` | Máximo de resultados |

**Response:**
```json
{
  "facts": [
    {
      "id": 1,
      "entity": "Eliandro",
      "fact_type": "preference",
      "content": "Prefere respostas diretas",
      "source_conversation_id": 42,
      "confidence": 0.9,
      "deprecated": false,
      "created_at": "2026-04-26T10:00:00"
    }
  ]
}
```

---

### `GET /api/facts/stats`

Estatísticas dos fatos extraídos.

**Response:**
```json
{
  "total": 25,
  "active": 22,
  "deprecated": 3,
  "by_type": {"preference": 8, "decision": 5, "contact": 4, "fact": 8}
}
```

---

### `POST /api/facts/extract/{conv_id}`

Dispara extração manual de fatos para uma conversa.

**Response:**
```json
{"status": "enqueued", "conversation_id": 42}
```

---

### `DELETE /api/facts/{fact_id}`

Deprecar (soft delete) um fato.

**Response:**
```json
{"status": "deprecated", "fact_id": 5}
```

**Erros:**

| Status | Descrição |
|---|---|
| `404` | Fato não encontrado |

---

### `GET /api/worker/stats`

Estatísticas do background worker.

**Response:**
```json
{
  "queue_size": 2,
  "processed": 150,
  "errors": 1
}
```

---

## Uso e Orçamento

### `GET /api/usage/budget`

Gastos do mês atual.

**Response:**
```json
{
  "spent_usd": 1.23,
  "limit_usd": 50.0
}
```

---

### `GET /api/usage/by-model`

Uso agrupado por modelo.

**Query Params:**

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `days` | int | `30` | Período em dias |

**Response:**
```json
{
  "usage": [
    {
      "model_id": "glm-5.1",
      "provider": "zai",
      "calls": 200,
      "input_tokens": 50000,
      "output_tokens": 30000,
      "total_cost": 0.155
    }
  ],
  "days": 30
}
```

---

### `GET /api/usage/daily`

Uso diário (série temporal).

**Query Params:**

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `days` | int | `30` | Período em dias |

**Response:**
```json
{
  "daily": [
    {"day": "2026-04-28", "calls": 15, "cost": 0.012, "tokens": 8500}
  ],
  "days": 30
}
```

---

## Observabilidade

### `GET /api/observability/overview`

Visão geral das métricas dos últimos N dias.

**Query Params:**

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `days` | int | `7` | Período |

---

### `GET /api/observability/by-model`

Quebra de uso/custo por modelo.

**Query Params:** `days` (default: 7)

---

### `GET /api/observability/by-agent`

Quebra de uso/custo por agente.

**Query Params:** `days` (default: 7)

---

### `GET /api/observability/cache`

Métricas detalhadas de prompt caching.

**Query Params:** `days` (default: 7)

---

### `GET /api/observability/timeline`

Série temporal de uso.

**Query Params:**

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `days` | int | `30` | Período |
| `granularity` | string | `"day"` | Granularidade: `"day"` ou `"hour"` |

---

### `GET /api/observability/top-conversations`

Conversas mais caras do último mês.

**Query Params:** `limit` (default: 10)

---

## Embeddings e Busca Semântica

### `POST /api/embeddings/reindex`

Dispara reindexação completa do vault para busca semântica.

**Response:**
```json
{"indexed": 25, "errors": 0, "duration_seconds": 3.5}
```

**Erros:**

| Status | Descrição |
|---|---|
| `501` | Embeddings não disponíveis |

---

### `GET /api/embeddings/stats`

Estatísticas do índice de embeddings.

**Response:**
```json
{
  "total_vectors": 45,
  "dimensions": 1536,
  "index_size_mb": 2.5,
  "last_indexed": "2026-04-29T10:00:00"
}
```

---

### `GET /api/embeddings/health`

Health check do serviço de embeddings.

**Response:**
```json
{"status": "ok", "provider": "ollama", "model": "nomic-embed-text"}
```

---

### `DELETE /api/cache/clear`

Limpa cache semântico de respostas.

**Query Params:**

| Parâmetro | Tipo | Default | Descrição |
|---|---|---|---|
| `older_than_days` | int? | `null` | Limpar só entradas mais velhas que N dias |

**Response:**
```json
{"removed": 15}
```

---

## Bridge OpenClaw

Ponte bidirecional entre ClawVault e OpenClaw.

### `GET /api/bridge/status`

Status da ponte e contagem de dados em cada lado.

**Response:**
```json
{
  "openclaw": {
    "workspace": "/root/.openclaw/workspace",
    "memory_md": true,
    "daily_logs": 30,
    "projects": 5
  },
  "clawvault": {
    "vault_root": "/root/.../vault",
    "wiki_notes": 25,
    "raw_notes": 5,
    "agent_notes": 3,
    "output_notes": 2
  },
  "sync": {
    "last_import": "2026-04-29T10:00:00",
    "last_export": "2026-04-29T09:00:00"
  }
}
```

---

### `POST /api/bridge/import`

Importa dados do workspace OpenClaw para o vault ClawVault:
- `MEMORY.md` → wiki/conceitos/
- `memory/*.md` → wiki/eventos/
- `projects/*/STATE.md` → wiki/projetos/
- `.learnings/*.md` → wiki/conceitos/

**Response:**
```json
{
  "status": "ok",
  "imported": ["MEMORY.md → 10_wiki/conceitos/openclaw-memory-geral.md"],
  "total": 12
}
```

---

### `POST /api/bridge/export`

Exporta conhecimento do ClawVault para o workspace OpenClaw.

**Response:**
```json
{
  "status": "ok",
  "exported": ["Vault wiki (25 notas) → clawvault-knowledge-base.md"],
  "total": 2
}
```

---

### `POST /api/bridge/sync`

Sincronização bidirecional completa (import + export).

**Response:**
```json
{
  "status": "ok",
  "import": { "...": "..." },
  "export": { "...": "..." },
  "timestamp": "2026-04-29T10:00:00"
}
```

---

## WhatsApp

Endpoints para integração com Evolution API (prefixo `/api/whatsapp`).

> **Nota:** Módulo opcional. Se não importável, rotas não são montadas.

### `POST /api/whatsapp/webhook`

Recebe webhooks da Evolution API com mensagens do WhatsApp.

### `GET /api/whatsapp/instance/{name}/qr`

Gera QR Code para parear instância.

### `POST /api/whatsapp/instance`

Cria nova instância WhatsApp.

---

## Modelos Pydantic

### `ChatRequest`
```python
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    agent_name: str = "main"
    model_override: Optional[str] = None
    compress: bool = True
```

### `ChatResponse`
```python
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
```

### `TranscribeRequest`
```python
class TranscribeRequest(BaseModel):
    audio_data: str       # base64 encoded
    mime_type: str = "audio/webm"
```

### `CreateAgentRequest`
```python
class CreateAgentRequest(BaseModel):
    name: str
    role: str
    parent_agent: str = "main"
    preferred_model: Optional[str] = None
    system_prompt: Optional[str] = None
```

### `SaveNoteRequest`
```python
class SaveNoteRequest(BaseModel):
    title: str
    content: str
    layer: str = "wiki"       # "raw" | "wiki" | "output"
    category: str = "conceitos"
    tags: list[str] = []
```

### `ShareMemoryRequest`
```python
class ShareMemoryRequest(BaseModel):
    namespace: str
    key: str
    content: str
    source_agent: str = "main"
    target_agents: Optional[list[str]] = None
    ttl_hours: Optional[int] = None
```

---

## Códigos de Erro

| Status | Quando |
|---|---|
| `200` | Sucesso |
| `400` | Parâmetro inválido, agente já existe, modo de busca inválido |
| `403` | Path traversal detectado (vault) |
| `404` | Recurso não encontrado (agente, nota, fato, conversa) |
| `500` | Erro interno (LLM falhou, transcrição falhou) |
| `501` | Feature não disponível (embeddings, facts não importados) |

---

## Rate Limits

Sem rate limits server-side. O throttling é feito pelo orçamento mensal (`MONTHLY_BUDGET_USD`) — quando excedido, o roteador automaticamente redireciona para modelos gratuitos/locais.

---

*Última atualização: 2026-04-29*
