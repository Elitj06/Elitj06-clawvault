# 🐾 ClawVault

> Sistema pessoal de agentes multi-LLM com memória persistente, roteamento inteligente e integração WhatsApp.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)

---

## Visão Geral

ClawVault é um assistente IA local com UI web. Backend em FastAPI, frontend em Next.js, memória em SQLite + markdown vault. Suporta 52 modelos de 11 providers com roteamento automático por complexidade.

**Diferenciais:**
- **Roteamento inteligente** — classifica cada pergunta (trivial→crítico) e escolhe o modelo mais barato que resolve
- **Memória persistente** — vault estilo Obsidian com wiki-links + memória hierárquica por agente
- **Function calling** — loop agentic com 5 tools integrados (web_fetch, api_call, vault_search, calculator, get_current_time)
- **Busca semântica** — embeddings via Ollama + cache semântico de respostas
- **WhatsApp nativo** — Evolution API com auto-resposta, digitação, rate limiting
- **Compressão transparente** — reduz prompts antes de enviar ao LLM

---

## Stack

| Camada | Tecnologia | Versão |
|---|---|---|
| Backend | Python + FastAPI + Uvicorn | 3.11+ / 0.110+ |
| Frontend | Next.js + React + TypeScript | 16 / 19 |
| Banco | SQLite (via stdlib) | — |
| Estilo | Tailwind CSS + Lucide Icons | 3.4+ |
| Gráficos | Recharts | 2.12+ |
| STT | Deepgram nova-3 (PT-BR) | REST direto |
| Embeddings | Ollama (local) / OpenAI | — |
| WhatsApp | Evolution API (Baileys) | — |

---

## Estrutura do Projeto

```
clawvault/
├── backend/                    # Python backend
│   ├── api/
│   │   ├── server.py           # FastAPI app — todas as rotas REST + WebSocket
│   │   └── bridge.py           # Ponte bidirecional OpenClaw ↔ ClawVault
│   ├── core/
│   │   ├── config.py           # Catálogo de 52 modelos, regras de roteamento, API keys
│   │   └── database.py         # SQLite helpers (db.initialize, db.fetch_all, etc.)
│   ├── llm/
│   │   ├── router.py           # Roteador inteligente — classifica e despacha
│   │   └── classifier.py       # Classificação em 3 camadas (regex → LLM → histograma)
│   ├── memory/
│   │   ├── manager.py          # Gerenciador de conversas e mensagens
│   │   ├── vault.py            # Segundo cérebro (markdown wiki)
│   │   ├── multi_agent.py      # Registry de agentes + memória compartilhada
│   │   └── auto_learn.py       # Auto-detecção de informações importantes
│   ├── tools/
│   │   ├── base.py             # Classe abstrata Tool (auto-registro)
│   │   ├── registry.py         # Registro central + dispatch
│   │   └── builtins.py         # 5 tools: web_fetch, api_call, vault_search, calculator, time
│   ├── channels/
│   │   └── whatsapp/           # Evolution API integration (webhook, client)
│   ├── compression/            # Compressor de prompts
│   ├── agents/                 # Protocolo AgentSpeak
│   ├── importers/              # Importação de dados do OpenClaw
│   ├── fact_extractor.py       # Extração automática de fatos
│   ├── background.py           # Background worker (fact extraction, etc.)
│   ├── embeddings.py           # Embeddings (Ollama/OpenAI)
│   ├── search.py               # Busca semântica + híbrida + cache
│   ├── stt.py                  # Speech-to-Text (Deepgram)
│   ├── slash_commands.py       # Comandos /help, /vault, etc.
│   ├── observability.py        # Métricas de uso e custo
│   └── requirements.txt        # Dependências Python
├── frontend/                   # Next.js dashboard
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx        # Home — visão geral
│   │   │   ├── chat/page.tsx   # Chat com agentes
│   │   │   ├── vault/page.tsx  # Vault explorer + brain graph
│   │   │   ├── agents/page.tsx # Gerenciar agentes
│   │   │   ├── usage/page.tsx  # Gráficos de uso
│   │   │   ├── settings/page.tsx # Configurações
│   │   │   └── whatsapp/page.tsx # WhatsApp management
│   │   ├── components/
│   │   │   ├── brain/BrainCanvas.tsx  # Grafo SVG animado
│   │   │   ├── Sidebar.tsx            # Navegação lateral
│   │   │   └── LayoutShell.tsx        # Layout wrapper
│   │   └── lib/api.ts          # Cliente API
│   └── package.json
├── vault/                      # Segundo cérebro (markdown)
│   ├── 00_raw/                 # Dados brutos
│   ├── 10_wiki/                # Conhecimento curado
│   │   ├── conceitos/          # Conceitos e definições
│   │   ├── eventos/            # Eventos e logs diários
│   │   ├── fatos/              # Fatos extraídos automaticamente
│   │   └── projetos/           # Estados de projetos
│   ├── 20_output/              # Conteúdo gerado
│   ├── 30_agents/              # Memória dos agentes
│   └── 99_index/               # Índices e links
├── data/                       # SQLite DB + backups
├── docs/                       # Documentação
├── scripts/                    # Scripts utilitários
│   ├── start.sh                # Iniciar backend + frontend
│   ├── systemd/                # Unit files para systemd
│   └── push-to-github.sh       # Push para GitHub
├── .env                        # Variáveis de ambiente (API keys)
└── README.md
```

---

## Como Rodar

### Pré-requisitos

- Python 3.11+
- Node.js 20+ (para o frontend)
- Opcional: Ollama (para embeddings locais e modelos locais)

### Instalação

```bash
# 1. Clone
git clone https://github.com/Elitj06/Elitj06-clawvault.git
cd Elitj06-clawvault/clawvault

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env — pelo menos UMA API key é necessária
# Recomendação: ZAI_API_KEY ou OPENROUTER_API_KEY

# 3. Instale dependências do backend
pip install -r backend/requirements.txt

# 4. Inicialize o banco
python -m backend.cli.main init

# 5. Inicie o backend
python -m backend.api.server
# Disponível em http://localhost:8000 (docs: /docs)

# 6. Em outro terminal, inicie o frontend
cd frontend
npm install
npm run dev
# Disponível em http://localhost:3000

# Ou use o script que sobe ambos:
./scripts/start.sh
```

### Produção (systemd)

```bash
# Copie os unit files
sudo cp scripts/systemd/clawvault-backend.service /etc/systemd/system/
sudo cp scripts/systemd/clawvault-frontend.service /etc/systemd/system/

# Ative e inicie
sudo systemctl daemon-reload
sudo systemctl enable --now clawvault-backend
sudo systemctl enable --now clawvault-frontend
```

---

## Variáveis de Ambiente

Configure no arquivo `.env` na raiz do projeto:

| Variável | Obrigatória | Descrição |
|---|---|---|
| `ZAI_API_KEY` | Recomendada | API key da Z.ai (GLM-5.1, GLM-4.7) |
| `BIGMODEL_API_KEY` | Opcional | GLM free tier (glm-4.5-flash grátis) |
| `GROQ_API_KEY` | Opcional | Groq (Llama, Qwen, Kimi — ultra rápido) |
| `OPENAI_API_KEY` | Opcional | OpenAI (GPT-5, GPT-4o) |
| `ANTHROPIC_API_KEY` | Opcional | Anthropic (Claude Opus, Sonnet, Haiku) |
| `GOOGLE_API_KEY` | Opcional | Google (Gemini 3 Pro, Flash) |
| `OPENROUTER_API_KEY` | Opcional | Gateway para 300+ modelos |
| `DEEPSEEK_API_KEY` | Opcional | DeepSeek V3 |
| `MOONSHOT_API_KEY` | Opcional | Moonshot/Kimi (262k contexto) |
| `MINIMAX_API_KEY` | Opcional | MiniMax M2.7, M2.5 |
| `DASHSCOPE_API_KEY` | Opcional | Alibaba Qwen (1M contexto) |
| `DEEPGRAM_API_KEY` | Opcional | Deepgram STT (transcrição de áudio) |
| `OLLAMA_HOST` | Opcional | URL do Ollama local (padrão: `http://localhost:11434`) |
| `DEFAULT_MODEL` | Opcional | Modelo padrão (padrão: `zai-glm-5.1`) |
| `MONTHLY_BUDGET_USD` | Opcional | Orçamento mensal em USD (padrão: `50.0`) |
| `DEBUG` | Opcional | Modo debug (padrão: `false`) |

> **Mínimo funcional:** apenas `ZAI_API_KEY` para usar GLM-5.1 como modelo principal + GLM-4.7-flash grátis para tarefas triviais.

---

## API Endpoints

O backend expõe a API REST em `http://localhost:8000`. O frontend faz proxy de `/api/*` para o backend via Next.js rewrites.

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/api/status` | Status geral (providers, budget, stats) |
| `GET` | `/api/models` | Lista modelos disponíveis |
| `POST` | `/api/chat` | Chat (sync) — principal endpoint |
| `POST` | `/api/chat/stream` | Chat (SSE streaming) |
| `WS` | `/ws/chat` | Chat via WebSocket |
| `POST` | `/api/transcribe` | Transcrição de áudio (Deepgram) |
| `GET` | `/api/commands` | Lista slash commands |
| `GET` | `/api/conversations` | Lista conversas |
| `GET` | `/api/conversations/{id}/messages` | Mensagens de uma conversa |
| `DELETE` | `/api/conversations/{id}` | Arquivar conversa |
| `GET` | `/api/agents` | Lista agentes |
| `POST` | `/api/agents` | Cria sub-agente |
| `GET` | `/api/agents/{name}` | Detalhes de um agente |
| `GET` | `/api/agents/{name}/memory` | Memória de um agente |
| `GET` | `/api/shared-memory/channels` | Canais de memória compartilhada |
| `POST` | `/api/shared-memory` | Publicar memória compartilhada |
| `GET` | `/api/vault/status` | Estatísticas do vault |
| `POST` | `/api/vault/notes` | Salvar nota no vault |
| `GET` | `/api/vault/search` | Buscar notas (keyword/semantic/hybrid) |
| `GET` | `/api/vault/notes/{path}` | Ler nota específica |
| `DELETE` | `/api/vault/notes/{path}` | Deletar nota |
| `GET` | `/api/vault/graph` | Grafo de conhecimento (para visualização) |
| `GET` | `/api/vault/entities` | Lista entidades do vault |
| `GET` | `/api/facts` | Lista fatos extraídos |
| `POST` | `/api/facts/extract/{conv_id}` | Disparar extração de fatos |
| `GET` | `/api/usage/budget` | Gastos do mês |
| `GET` | `/api/usage/by-model` | Uso por modelo |
| `GET` | `/api/usage/daily` | Uso diário |
| `GET` | `/api/observability/*` | Métricas detalhadas |
| `POST` | `/api/embeddings/reindex` | Reindexar vault para busca semântica |
| `GET` | `/api/bridge/status` | Status da ponte OpenClaw |
| `POST` | `/api/bridge/import` | Importar dados do OpenClaw |
| `POST` | `/api/bridge/export` | Exportar dados para OpenClaw |
| `POST` | `/api/bridge/sync` | Sincronização bidirecional |

> Documentação interativa completa em `http://localhost:8000/docs` (Swagger UI).

---

## Roteamento de Modelos

Cada mensagem é classificada em 5 níveis. O roteador seleciona o modelo mais barato disponível:

| Nível | Descrição | Modelo primário |
|---|---|---|
| `TRIVIAL` | Saudações, comandos curtos | GLM-4.5-flash (grátis) |
| `SIMPLE` | Perguntas factuais, lookup | Z.ai GLM-5.1 |
| `MEDIUM` | Análise, código, escrita | Z.ai GLM-5.1 → Groq Kimi K2 |
| `COMPLEX` | Arquitetura, debug profundo | Z.ai GLM-5.1 → Groq Kimi K2 |
| `CRITICAL` | Decisões de negócio, produção | Z.ai GLM-5.1 → Groq Kimi K2 |

Fallback automático: se o modelo primário falhar, tenta o próximo da lista. Se todos falharem, erro é retornado.

---

## Function Calling (Tools)

O sistema suporta function calling com loop agentic (máximo 5 iterações):

| Tool | Descrição |
|---|---|
| `web_fetch` | Busca conteúdo de uma URL |
| `api_call` | Faz requisições HTTP (GET/POST/PUT/DELETE) |
| `vault_search` | Busca no knowledge base local |
| `calculator` | Avalia expressões matemáticas seguras |
| `get_current_time` | Retorna data/hora em timezone específica |

---

## Frontend (Dashboard)

O dashboard web inclui:

- **Home** — visão geral de custos, providers, estatísticas
- **Chat** — conversar com qualquer agente, upload de arquivos, gravação de áudio
- **Vault** — explorar notas, brain graph interativo, busca
- **Agentes** — gerenciar agentes e sub-agentes
- **Uso** — gráficos de custo e uso por modelo/período
- **WhatsApp** — QR code, contatos, configurações
- **Configurações** — status dos providers, modelos disponíveis

Tema dark cyber-minimalista (#111827, #A78BFA, #4ADE80). Responsivo para mobile.

---

## Proxies e Deploy

O frontend faz proxy automático de `/api/*` para o backend:

```typescript
// frontend/next.config.ts
async rewrites() {
  return [{ source: "/api/:path*", destination: "http://5.78.198.180:8000/api/:path*" }];
}
```

Para produção, altere o IP no `next.config.ts` e no `frontend/.env.production`.

---

## Documentação

- [`docs/INSTALACAO.md`](docs/INSTALACAO.md) — Guia completo de instalação
- [`docs/API.md`](docs/API.md) — Referência completa da API REST
- [`docs/MEMORIA-MULTI-AGENTE.md`](docs/MEMORIA-MULTI-AGENTE.md) — Arquitetura de memória
- `http://localhost:8000/docs` — Swagger UI interativo

---

## Licença

Projeto pessoal. Uso livre para fins pessoais.

---

## Autor

Construído por **Eliandro Tjader** com auxílio de IA.
