# 🚀 Guia de Instalação — ClawVault

Este guia mostra **exatamente** o que você precisa fazer para ter o ClawVault
rodando na sua máquina. Copie e cole os comandos.

---

## ✅ Pré-requisitos

1. **Python 3.11 ou superior**
   - Windows: baixe em https://www.python.org/downloads/
   - Durante a instalação, **marque a caixa "Add Python to PATH"**
   - Para verificar: abra o terminal e rode `python --version`

2. **Git** (opcional, só se for clonar de repositório)

---

## 📥 Passo 1: Baixar os arquivos

Coloque a pasta `clawvault/` em um local de fácil acesso. Exemplo:
- Windows: `C:\Users\Eliandro\clawvault\`
- Linux/Mac: `/home/eliandro/clawvault/`

---

## 🔧 Passo 2: Instalar as dependências

Abra o terminal **dentro da pasta clawvault**:

```bash
# Windows (PowerShell ou CMD)
cd C:\Users\Eliandro\clawvault

# Linux/Mac (Terminal)
cd /home/eliandro/clawvault
```

Instale as bibliotecas Python:

```bash
pip install -r backend/requirements.txt
```

**Se der erro de permissão no Linux/Mac:**
```bash
pip install -r backend/requirements.txt --break-system-packages
```

---

## 🔑 Passo 3: Configurar suas chaves de API

1. Na pasta `clawvault/`, **copie** o arquivo `.env.example` e **renomeie** para `.env`

   ```bash
   # Windows
   copy .env.example .env

   # Linux/Mac
   cp .env.example .env
   ```

2. Abra o arquivo `.env` no seu editor de texto (Notepad, VS Code, etc)

3. Cole suas chaves nos campos correspondentes. **Você precisa de pelo menos UMA.**

### 🎯 Recomendações de chaves

**Começando com orçamento zero (100% grátis):**
- `OPENROUTER_API_KEY` — cadastre em https://openrouter.ai (8 modelos grátis)
- `ZAI_API_KEY` — cadastre em https://z.ai/model-api (2 modelos grátis)
- `GROQ_API_KEY` — cadastre em https://console.groq.com (30 req/min sem cartão)

**Começando com qualidade premium:**
- `ANTHROPIC_API_KEY` — https://console.anthropic.com (Claude direto)
- `OPENROUTER_API_KEY` — fallback barato para tudo mais

**Exemplo de `.env` mínimo funcional:**

```
OPENROUTER_API_KEY=sk-or-v1-abc123...
ANTHROPIC_API_KEY=sk-ant-api03-xyz789...
DEFAULT_MODEL=claude-sonnet-4-6
MONTHLY_BUDGET_USD=30.0
```

---

## 🎬 Passo 4: Inicializar o sistema

Na pasta `clawvault/`, rode:

```bash
python -m backend.cli.main init
```

Você deve ver:
- ✅ Banco de dados criado
- ✅ Pastas do vault criadas
- ✅ Lista das suas chaves configuradas

---

## 💬 Passo 5: Testar com uma pergunta rápida

```bash
python -m backend.cli.main ask "Qual a capital do Brasil?" --show-cost
```

O sistema vai:
1. Classificar a pergunta como TRIVIAL
2. Usar o modelo mais barato disponível (provavelmente um grátis)
3. Mostrar a resposta e o custo real

---

## 🗣️ Passo 6: Iniciar chat interativo

```bash
python -m backend.cli.main chat --title "Meu primeiro chat"
```

**Comandos dentro do chat:**
- Digite normalmente para conversar
- `/modelo claude-opus-4-7` — forçar um modelo específico
- `/modelo` (sem nome) — voltar ao roteamento automático
- `/custo` — ver quanto gastou nesta conversa
- `/limpar` — limpar memória quente
- `/salvar Título` — renomear a conversa
- `sair` — encerrar

---

## 📋 Comandos úteis

```bash
# Ver todos os modelos disponíveis
python -m backend.cli.main models

# Ver só modelos que você pode usar agora (com chave configurada)
python -m backend.cli.main models --available-only

# Ver gastos do mês
python -m backend.cli.main budget

# Ver status geral
python -m backend.cli.main status

# Buscar em conversas anteriores
python -m backend.cli.main search "GymFlow"
```

## 🤖 Comandos multi-agente (segundo cérebro)

Para detalhes completos, veja `docs/MEMORIA-MULTI-AGENTE.md`.

```bash
# --- AGENTES ---
# Listar todos os agentes
python -m backend.cli.main agents list

# Criar sub-agente especializado
python -m backend.cli.main agents create code-reviewer \
  --role "Revisor de código Python/TS" --parent main

# Ver detalhes + memória de um agente
python -m backend.cli.main agents show code-reviewer

# --- MEMÓRIA PROGRESSIVA ---
# Adicionar fato fundamental (sempre no contexto)
python -m backend.cli.main memory add main "foco" \
  "Priorizo clareza sobre elegância" --level core

# Ver memória de um agente
python -m backend.cli.main memory show main

# --- MEMÓRIA COMPARTILHADA ---
# Publicar contexto compartilhado entre agentes
python -m backend.cli.main memory share \
  "project:gymflow" "stack" "Next.js + Supabase + Prisma"

# Listar canais ativos
python -m backend.cli.main memory channels

# Encaminhar contexto para nova tarefa
python -m backend.cli.main memory forward \
  "project:gymflow" "task:review-pr-123"

# --- VAULT (SEGUNDO CÉREBRO) ---
# Ver estatísticas do vault
python -m backend.cli.main vault status

# Salvar nota com wiki-links [[entre páginas]]
python -m backend.cli.main vault save --title "GymFlow" \
  --content "SaaS. Stack: [[Next.js]] + [[Supabase]]" \
  --layer wiki --category projetos

# Buscar no vault
python -m backend.cli.main vault search "supabase"

# Reconstruir grafo de conexões
python -m backend.cli.main vault graph

# --- IMPORTAR DO OPENCLAW ---
# Auto-detectar e importar
python -m backend.cli.main import-openclaw

# Ou especificar caminho
python -m backend.cli.main import-openclaw --path ~/.openclaw
```

---

## 🐛 Problemas comuns

### "ModuleNotFoundError: No module named 'backend'"
Você está rodando de fora da pasta `clawvault/`. Navegue até ela primeiro com `cd`.

### "Biblioteca 'anthropic' não instalada"
Rode: `pip install anthropic` (ou o nome da biblioteca que apareceu no erro)

### "Nenhum modelo disponível"
Você não configurou nenhuma chave de API no `.env`. Volte ao Passo 3.

### Chave errada / não funciona
Verifique se colou a chave inteira sem espaços extras no início ou fim.
As chaves da Anthropic começam com `sk-ant-`, OpenAI com `sk-proj-`, etc.

---

## 🎓 Próximos passos

Depois que tudo estiver funcionando:

1. **Explore modelos grátis** — tente `--model openrouter-free-auto`
2. **Compare custos** — veja `budget` após cada conversa
3. **Experimente roteamento** — faça perguntas de complexidade variada e
   veja o sistema escolher modelos diferentes automaticamente
4. **Aguarde a Entrega 2** — dashboard web e importador do OpenClaw

Qualquer dúvida, é só chamar!
