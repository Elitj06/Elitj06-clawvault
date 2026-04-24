# 🧠 Arquitetura de Memória Multi-Agente

Este documento explica como funciona a memória do ClawVault — o que torna o
sistema um **segundo cérebro real**, com agentes que aprendem e
compartilham conhecimento entre si sem estourar o orçamento de tokens.

---

## 🎯 O problema que estamos resolvendo

Sistemas tradicionais com LLM sofrem de **três problemas de memória**:

1. **Esquecimento total:** cada conversa começa do zero. Você repete tudo.
2. **Inchaço de contexto:** quando guarda memória, manda tudo junto e cada
   chamada fica cada vez mais cara.
3. **Agentes isolados:** sub-agentes não sabem o que o principal aprendeu.

O ClawVault resolve os três simultaneamente.

---

## 🏗️ As 3 camadas do sistema

### Camada 1: Vault (Segundo Cérebro) — estilo Obsidian

Todo conhecimento estruturado fica em markdown, legível fora do sistema:

```
vault/
├── 00_raw/         📥 Dados brutos (conversas, PDFs, clippings)
├── 10_wiki/        🌐 Conhecimento curado com links [[entre]] páginas
│   ├── pessoas/
│   ├── projetos/
│   ├── conceitos/
│   └── empresas/
├── 20_output/      📤 Conteúdo gerado (drafts, publicado, descartado)
├── 30_agents/      🤖 Memória de cada agente
├── 40_skills/      ⚡ Padrões aprendidos reutilizáveis
└── 99_index/       🗂️ Grafo de conexões (links.json)
```

**Filosofia:** separar radicalmente `raw` (fonte da verdade, nunca edita) de
`wiki` (conhecimento trabalhado) de `output` (produto final). Isso impede
que o vault vire uma pasta bagunçada.

**Wiki-links `[[nome]]`:** todo texto em `10_wiki/` pode citar outras notas
com `[[GymFlow]]` ou `[[Supabase]]`. O sistema escaneia isso e monta um
**grafo de conexões** automaticamente — igual no Obsidian.

Comandos:

```bash
# Ver status do vault
python -m backend.cli.main vault status

# Salvar uma nota no wiki
python -m backend.cli.main vault save --title "GymFlow" \
  --content "SaaS para academias. Stack: [[Next.js]] + [[Supabase]]" \
  --layer wiki --category projetos

# Buscar
python -m backend.cli.main vault search "supabase"

# Reconstruir grafo
python -m backend.cli.main vault graph
```

---

### Camada 2: Memória Progressiva de cada Agente

Cada agente (principal ou sub-agente) tem **3 níveis** de memória própria
que crescem de forma otimizada:

```
⭐ CORE      (~500 tokens)  → sempre vai no contexto
📚 LEARNED   (~2000 tokens) → vai quando relevante
💭 EPISODIC  (ilimitado)    → últimas 50 experiências
```

**Como cresce sem inchar:**

1. Toda interação vira uma **memória episódica** (barato, só um INSERT).
2. A cada **10 episódicas**, um modelo **grátis** (Z.ai Flash) destila
   essas experiências em **1-3 padrões LEARNED** genéricos e reutilizáveis.
3. As episódicas consolidadas são **removidas** (viraram sabedoria, não
   precisam mais).
4. Padrões LEARNED que ficam 30 dias sem uso podem ser **podados**.
5. Apenas fatos **fundamentais** vão para CORE manualmente.

**Economia:** em vez de enviar 50 interações anteriores a cada chamada
(~15.000 tokens), o agente manda só CORE + LEARNED relevantes (~1.500
tokens). **Economia de ~90%.**

Comandos:

```bash
# Criar sub-agente
python -m backend.cli.main agents create code-reviewer \
  --role "Revisor de código Python/TS" \
  --parent main

# Adicionar memória a um agente
python -m backend.cli.main memory add code-reviewer \
  "foco" "Priorize legibilidade sobre micro-otimizações" \
  --level core --relevance 10

# Ver memória de um agente
python -m backend.cli.main memory show code-reviewer

# Ver status completo de um agente
python -m backend.cli.main agents show code-reviewer
```

---

### Camada 3: Shared Memory Bus — canal entre agentes

Este é o **diferencial que você pediu.** É como o agente principal
compartilha conhecimento específico com sub-agentes sem enviar tudo.

**Namespaces** (escopos):

- `project:gymflow` → tudo sobre o projeto GymFlow
- `project:marketplace` → tudo sobre o Marketplace Saúde
- `task:review-pr-123` → contexto de uma tarefa específica
- `entity:eliandro` → informações pessoais
- `skill:prisma` → como usar Prisma

**Fluxo típico:**

```
Agente principal analisa situação
   ↓
   Publica no bus: "project:gymflow"
      - stack: "Next.js 15 + Supabase"
      - priority: "E2E test antes do deploy"
   ↓
Cria sub-agente 'code-reviewer' para revisar PR
   ↓
Sub-agente consulta bus.fetch("project:gymflow")
   ↓
Recebe SÓ o contexto do projeto, não o vault inteiro
```

**Encaminhamento** (forward):

Quando uma nova tarefa surge dentro de um projeto, você encaminha as
memórias relevantes para um namespace específico da tarefa:

```bash
# Encaminha contexto do projeto para uma tarefa nova
python -m backend.cli.main memory forward \
  "project:gymflow" "task:review-pr-123"
```

Isso cria um escopo isolado onde o sub-agente trabalha sem poluir o canal
principal do projeto.

Comandos:

```bash
# Publicar memória compartilhada
python -m backend.cli.main memory share \
  "project:gymflow" "stack" "Next.js + Supabase + Prisma"

# Listar canais ativos
python -m backend.cli.main memory channels

# Encaminhar contexto
python -m backend.cli.main memory forward \
  "project:gymflow" "task:fix-bug-coin-counter"
```

---

## 🔄 Exemplo prático: revisando um PR

Fluxo real de como as 3 camadas trabalham juntas quando você pede para
revisar um PR do GymFlow:

```
1. Você → Agente principal:
   "Revise o PR #123 do GymFlow, foco em segurança"

2. Agente principal:
   - Busca no vault wiki [[GymFlow]] → contexto do projeto
   - Busca no vault [[security-practices]] → padrões pessoais
   - Publica em "task:pr-123":
       * "stack: Next.js + Supabase"
       * "hot_paths: /api/checkin, /api/coins"
       * "never_expose: SUPABASE_SERVICE_ROLE_KEY"

3. Agente principal cria sub-agente 'pr-reviewer':
   - Herda CORE do 'code-reviewer' (ex: "priorize legibilidade")
   - Recebe do bus o contexto específico da task

4. Sub-agente trabalha:
   - Contexto enviado ao LLM: ~800 tokens
   - (sem memória: ~8000 tokens teriam sido enviados)
   - Economia: ~90%

5. Após a revisão:
   - Experiência vira EPISODIC do pr-reviewer
   - Se um padrão se repetir 10x, vira LEARNED
   - Conclusão importante vira nota no vault/20_output/
```

---

## 📊 Comparação: com vs sem este sistema

| Cenário | Sem ClawVault | Com ClawVault |
|---|---|---|
| 1ª revisão de PR do GymFlow | ~10k tokens | ~10k tokens |
| 10ª revisão (mesmo projeto) | ~10k tokens (repete tudo) | ~1.5k tokens |
| Novo sub-agente para mesma área | ~10k tokens | ~1.5k tokens |
| Custo mensal estimado | $50 | $8-12 |

---

## 🎓 Conceitos inspirados

Esta arquitetura combina o melhor de três abordagens:

- **Obsidian:** vault em markdown + wiki-links + grafo de conexões
- **Hermes Agent:** learning loop + memória progressiva + sub-agentes isolados
- **OpenClaw:** skills reutilizáveis como arquivos markdown

Mas **nada é puxado automaticamente da internet.** Tudo roda local no seu
computador ou VPS. Sem mensalidade externa.

---

## ⚙️ Evolução prevista

Esta é a v0.1 da arquitetura multi-agente. Melhorias planejadas:

- **Embeddings locais** para busca semântica real no vault (não só keyword)
- **Auto-promoção:** padrões LEARNED muito usados viram CORE automaticamente
- **Prune inteligente:** remove memórias duplicadas após consolidação
- **Dashboard visual** do grafo de conhecimento (Entrega 2)
