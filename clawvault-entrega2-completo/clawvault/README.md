# 🐾 ClawVault

> Sistema pessoal de agentes multi-LLM com memória persistente, roteamento inteligente e integração WhatsApp — construído para economizar tokens sem perder qualidade.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![Status](https://img.shields.io/badge/Status-v0.2.0-orange.svg)]()

---

## 💡 O que é

ClawVault é uma alternativa self-hosted ao OpenClaw e Hermes Agent, criada com três obsessões:

1. **Economia de tokens** — roteamento automático entre 52 modelos de 11 providers, escolhendo sempre o mais barato que atende
2. **Memória real** — vault estilo Obsidian + memória progressiva por agente que aprende sem inchar
3. **WhatsApp nativo** — integração com Evolution API para atendimento automatizado em português

Este é um projeto pessoal, feito por e para um empreendedor. Não é um SaaS.

---

## 🎯 Diferenciais

### Roteamento inteligente de LLMs

Cada pergunta é classificada em 5 níveis de complexidade. O sistema escolhe o modelo mais barato que dá conta:

| Complexidade | Vai para |
|---|---|
| 🟢 Trivial | GLM-4.7-flash **grátis** (Z.ai) |
| 🟢 Simples | Llama 3.3 70B **grátis** (OpenRouter) |
| 🟡 Média | MiniMax M2.5 ($0.28/M) |
| 🟠 Complexa | Claude Sonnet 4.6 |
| 🔴 Crítica | Claude Opus 4.7 |

**Resultado típico:** 60-70% de economia vs. usar sempre um modelo premium.

### Memória hierárquica de 4 camadas

- **Quente** (RAM): últimas 20 mensagens
- **Morna** (SQLite): últimos 7 dias
- **Fria** (Vault markdown com wiki-links): 7-90 dias
- **Arquivo** (comprimido): +90 dias

### Memória compartilhada entre agentes

O agente principal publica contexto em "canais" (namespaces) e sub-agentes consomem apenas o relevante para sua tarefa. **Sub-agentes não carregam memórias que não precisam.**

### Segundo cérebro estilo Obsidian

```
vault/
├── 00_raw/      Dados brutos
├── 10_wiki/     Conhecimento com [[wiki-links]]
├── 20_output/   Conteúdo gerado
└── 99_index/    Grafo de conexões
```

Tudo markdown, legível fora do sistema.

### Compressão humana → máquina

Quando você escreve *"Por favor, você poderia me ajudar a revisar este código..."*, o sistema comprime transparente para **"revisar este código"** antes de enviar ao LLM. Você escreve natural, o sistema economiza.

---

## 📦 Stack

**Backend:**
- Python 3.11+ / FastAPI / SQLite / Pydantic
- SDKs: Anthropic, OpenAI (compatível com Z.ai, Groq, Moonshot, MiniMax, Alibaba, OpenRouter, DeepSeek), Google

**Frontend:**
- Next.js 15 (App Router) / React 19 / TypeScript
- Tailwind CSS / Recharts / Lucide Icons

**Integrações:**
- Evolution API (WhatsApp via Baileys)
- Ollama (modelos locais)

---

## 🚀 Instalação rápida

### Pré-requisitos

- Python 3.11+
- Node.js 20+ (para o dashboard)
- Docker (opcional, para Evolution API do WhatsApp)

### Passos

```bash
# 1. Clone
git clone https://github.com/Elitj06/Elitj06-clawvault.git
cd Elitj06-clawvault

# 2. Configure
cp .env.example .env
# Edite .env e coloque pelo menos UMA chave de API
# Recomendação: OPENROUTER_API_KEY (300+ modelos numa só chave)

# 3. Backend
pip install -r backend/requirements.txt
python -m backend.cli.main init

# 4. Teste pelo CLI
python -m backend.cli.main chat

# 5. Ou suba o servidor API + dashboard
python -m backend.api.server
# (em outro terminal)
cd frontend && npm install && npm run dev

# Acesse http://localhost:3000
```

Guia detalhado em [`docs/INSTALACAO.md`](docs/INSTALACAO.md).

---

## 🎬 Dashboard

O dashboard web (`localhost:3000`) inclui:

- **Visão geral** — custos, providers, gráfico de gastos
- **Chat** — conversar com qualquer agente, ver modelo usado e custo em tempo real
- **Agentes** — gerenciar agentes/sub-agentes, ver memória progressiva
- **Vault** — explorar notas, buscar, ver grafo de conexões
- **WhatsApp** — QR Code, contatos, configurações de atendimento
- **Uso e custos** — gráficos detalhados por modelo e período
- **Configurações** — status de providers, modelos disponíveis

---

## 📱 WhatsApp

Integração via [Evolution API](https://doc.evolution-api.com/) self-hosted:

```bash
# 1. Rode o Evolution API (Docker)
docker run -d --name evolution -p 8080:8080 \
  -e AUTHENTICATION_API_KEY=SUA_CHAVE_FORTE \
  atendai/evolution-api:latest

# 2. Configure no .env
EVOLUTION_BASE_URL=http://localhost:8080
EVOLUTION_API_KEY=SUA_CHAVE_FORTE

# 3. No dashboard, vá em WhatsApp → Criar instância → Escanear QR Code

# 4. Pronto! Mensagens recebidas disparam auto-resposta via LLM
```

**Funcionalidades do módulo WhatsApp:**
- Auto-resposta com IA
- Simulação de "digitando..."
- Marca mensagens como lidas
- Rate limiting por contato
- Horário comercial configurável
- Bloqueio/desbloqueio de contatos
- Saudação automática no primeiro contato
- Suporte a grupos (opcional)

⚠️ **Aviso:** Evolution API usa Baileys (conexão não-oficial). Meta pode banir números. Use chip dedicado, não pessoal.

---

## 💰 Providers de LLM suportados

52 modelos catalogados, 12 grátis. Uma única chave do OpenRouter já te dá acesso a 300+ modelos.

| Provider | Modelos destacados | Grátis? |
|---|---|---|
| **OpenRouter** | Gateway para 300+ modelos | ✅ 8 modelos grátis |
| **Anthropic** | Opus 4.7, Sonnet 4.6, Haiku 4.5 | — |
| **OpenAI** | GPT-5, GPT-5-mini, GPT-4.1, GPT-4o | — |
| **Google** | Gemini 3 Pro, Gemini 2.5 Flash | ✅ Flash Lite |
| **Z.ai (GLM)** | GLM-5.1, GLM-4.7, GLM-4.7-flash | ✅ 2 modelos |
| **Groq** | Llama 70B, GPT-OSS, Kimi — tudo ultra rápido | ✅ Free tier |
| **Moonshot** | Kimi K2.6 (262k contexto) | — |
| **MiniMax** | M2.7, M2.5 (excelente em código) | — |
| **Alibaba** | Qwen 3.6 Max, Qwen 3 Coder | — |
| **DeepSeek** | DeepSeek V3 | — |
| **Ollama** | Qwen 2.5 Coder, Llama 3.2 (local) | ✅ Sempre |

---

## 📚 Estrutura

```
clawvault/
├── backend/              Python + FastAPI
│   ├── core/             Config, database
│   ├── llm/              Roteador, classificador
│   ├── memory/           Manager, vault, multi-agente
│   ├── compression/      Compressor humano→máquina
│   ├── agents/           Protocolo AgentSpeak
│   ├── importers/        Importador OpenClaw
│   ├── channels/         WhatsApp (Evolution API)
│   ├── api/              Servidor FastAPI
│   └── cli/              Interface terminal
├── frontend/             Next.js 15 dashboard
├── docs/                 Documentação em português
├── scripts/              Scripts utilitários
└── vault/                Seu vault (criado na instalação)
```

---

## 📖 Documentação

- [`docs/INSTALACAO.md`](docs/INSTALACAO.md) — Guia completo de instalação
- [`docs/MEMORIA-MULTI-AGENTE.md`](docs/MEMORIA-MULTI-AGENTE.md) — Arquitetura de memória

---

## 🗺️ Roadmap

- [x] **v0.1** — CLI + roteador multi-LLM + memória hierárquica
- [x] **v0.2** — Dashboard web + WhatsApp (este release)
- [ ] **v0.3** — Integrações: Telegram, Email, Google Calendar
- [ ] **v0.4** — Embeddings locais + busca semântica real
- [ ] **v0.5** — Auto-promoção de padrões + skills auto-geradas

---

## 🧠 Inspirações

ClawVault combina ideias de:
- **OpenClaw** — skills como arquivos markdown
- **Hermes Agent** — learning loop, memória progressiva, sub-agentes isolados
- **Obsidian** — vault + wiki-links + grafo de conexões
- **Karpathy's LLM Wiki** — arquitetura raw/wiki/output

---

## ⚖️ Licença

Projeto pessoal, uso livre para fins pessoais. Para uso comercial, entre em contato.

---

## ❤️ Autor

Construído por **Eliandro** com auxílio de Claude (Anthropic).
