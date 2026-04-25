---
title: OpenClaw Memory (Geral)
created: 2026-04-25 02:47
source: openclaw
layer: wiki
tags: [openclaw, memoria, sincronizado]
---

# OpenClaw — Memória Geral

# MEMORY.md — TJ Long-term Memory (REFERENCE FILE)

⚠️ **Para sessões normais, usar MEMORY-COMPACT.md. Este arquivo é referência detalhada.**

> Índice rápido. Para detalhes de projeto, ler o STATE.md correspondente.
> **Última atualização:** 2026-04-13

---

## Identidade

- Sou TJ, sistema de inteligência operacional do Eliandro Tjader
- Falo português com o Eliandro, direto e sem frescura
- Esposa: Isabella (Bella) — WhatsApp +5521986352883

---

## Projetos ativos

| Projeto | STATE | Status |
|---|---|---|
| fitflow-suite | `projects/fitflow-suite/STATE.md` | Em desenvolvimento — deploy ativo em fitflow-suite.vercel.app |
| compras-coletivas | `projects/compras-coletivas/STATE.md` | ✅ API online — Supabase, agente guia-compras ativo no grupo |
| pawsvibe | `projects/pawsvibe/STATE.md` | Iniciado 2026-03-28 — canal pets+humor, faceless com persona virtual |
| rise | `projects/rise/STATE.md` | ⏸️ PAUSADO 2026-04-05 — redes sociais, agente: influencie |

---

## Infraestrutura — Estado atual (2026-03-30)

### Evolution API (WhatsApp) — 2 instâncias
- **orion** → ownerJid `5521986053944` (WhatsApp pessoal do Eliandro) — ATIVO
- **tj** → ownerJid `5521999007170` (TJ — número de negócio) — ATIVO
- Versão instalada: **2.3.7** (mais recente — verificado 2026-04-01)
- Banco migrado de PostgreSQL Docker local → **Supabase** (schema `evolution`, aws-0-us-west-2)
- Container rodando via `docker run` (não docker-compose — bug v1.29 com imagem nova)
- Padrão de reconexão 499: esperado — app mobile sendo suspenso pelo SO (auto-recupera em 3-5s)

### Grupos WhatsApp conhecidos
- `120363424571639963@g.us` → grupo APP (Laura + Rafael + Cruz — FitFlow) — **agente: laura**
- `120363407495417777@g.us` → grupo Rise (TJ + Eliandro + Bella) — `requireMention: false` — **agente: main (TJ)**
- `120363408849824697@g.us` → grupo OpenClaw | CB (Cultura Builder — instância pessoal)
- `120363427493094672@g.us` → grupo "Passando a guarda" — 3 participantes (TJ + Eliandro + +5521997767313) — **agente: laura**
- `120363424457099212@g.us` → grupo "Teste Groq" — **agente: teste-groq** (clone GLM)
- `120363405060387448@g.us` → grupo Compras Coletivas — **agente: guia-compras**

### Agentes configurados
⚠️ Google/Gemini DESATIVADO — créditos GCP não cobrem API Gemini. Usar Anthropic + Z.AI (GLM) + Groq.

| Agente | Modelo primário | Fallbacks | Uso |
|---|---|---|---|
| main (TJ) | `zai/glm-5.1` | `openai/gpt-4.1-mini`, `openrouter/qwen3-next-80b`, `groq/qwen3-32b`, `groq/llama-3.3-70b` | Orquestrador principal |
| strategist | `openrouter/anthropic/claude-opus-4.6` | `openai/gpt-4.1`, `zai/glm-5.1`, `groq/qwen3-32b` | Estratégia, ideação, novos projetos |
| fitflow | `zai/glm-5` | `openai/gpt-4.1-mini`, `zai/glm-4.5-air`, `groq/qwen3-32b` | Dev FitFlow Suite |
| search | `zai/glm-4.5-air` | `openai/gpt-4.1-nano`, `groq/qwen3-32b`, `groq/llama-3.3-70b` | Pesquisas rápidas |
| memory | `zai/glm-4.5-air` | `openai/gpt-4.1-nano`, `groq/qwen3-32b`, `groq/llama-3.3-70b` | Gestão de memória |
| scout | `zai/glm-4.5-air` | `openai/gpt-4.1-nano`, `groq/qwen3-32b`, `groq/llama-3.3-70b` | Inteligência de mercado IA (semanal seg 06:30 UTC) |
| influencie | `zai/glm-4.5-air` | `openai/gpt-4.1-nano`, `groq/qwen3-32b`, `groq/llama-3.3-70b` | Redes sociais Rise/Pawsvibe |
| laura | `openai/gpt-4.1-nano` | `zai/glm-4.5-air`, `groq/qwen3-32b`, `groq/llama-3.3-70b` | Atendente grupo APP — GPT-4.1-nano (migrado 14/04) |
| soe | `zai/glm-4.5-air` | `openai/gpt-4.1-nano`, `groq/qwen3-32b`, `groq/llama-3.3-70b` | Relatórios SOE |
| tec-saude | `zai/glm-5.1` | `openai/gpt-4.1`, `openai/gpt-4.1-mini`, `zai/glm-5-turbo`, `groq/qwen3-32b` | Tec Saúde |

### OpenAI — integrado 2026-04-14
- **Tier 1** ($5 pagos): 500 RPM, 200K TPM, $100/mês spending
- **Modelos configurados:** gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-4o, gpt-4o-mini, o3-mini
- **Uso:** 1º fallback de todos os agentes + primário da Laura (gpt-4.1-nano)
- **Estratégia de fallback quádrupla:** Z.AI → OpenAI → OpenRouter → Groq

### Clones Z.AI (GLM primary + Groq fallback)
- **TJ Clone** → `tj-groq` (GLM-5 + Groq)
- **FitFlow Clone** → `fitflow-groq` (GLM-5.1 + Groq)
- **Laura Clone** → `laura-groq` (GLM-4.5-Air + Groq)
- **Strategist Clone** → `strategist-glm` (GLM-5.1 + Groq)
- **Memory Clone** → `memory-groq` (GLM-4.5-Air + Groq)
- **SOE Clone** → `soe-groq` (GLM-4.5-Air + Groq)

### Google Cloud fitflow-ia
- Billing ativo, R$1.759 em créditos até junho
- **⚠️ Créditos GCP NÃO cobrem API Gemini** — R$192 cobrados. NUNCA usar Google/Gemini como modelo de IA.

### Z.AI — integrado 2026-04-05
- **API Key:** `67e7b6ffe5cf40bfb9a6983a0561399a.vV7lNFe7Ze7V9p7a`
- **Plano:** Pro (Coding Plan)
- **Endpoint correto:** `https://api.z.ai/api/coding/paas/v4` ⚠️ NÃO usar `/api/paas/v4` (pay-per-use, exige saldo avulso)
- **Modelos disponíveis:** glm-4.5-air, glm-4.5, glm-4.6, glm-4.7, glm-5, glm-5-turbo, glm-5.1
- **Provider OpenClaw:** `zai` (configurado)
- **Qualidade PT-BR:** boa — testado glm-5 e glm-4.5-air com resposta fluente
- **Uso sugerido:** glm-4.5-air como fallback econômico; glm-5 como alternativa ao Sonnet
- **Estratégia de fallback tripla:** Sonnet → GLM → Groq (garante alta disponibilidade)

### Crons configurados (horário BRT)
| Job | Horário | Agente |
|---|---|---|
| Scout — mercado IA | Toda segunda 03:00 BRT | scout |
| Monitor — infra | A cada 6h | monitor |
| Revisão MEMORY.md | Toda segunda 02:00 | main |
| Verificação modelos | Todo dia 1 às 04:00 | monitor |

### TTS — Vozes configuradas
- **TJ:** `vits-piper-pt_BR-faber-medium` (Sherpa-ONNX v1.12.23, offline)
- **Laura:** `vits-piper-pt_BR-dii-high` (Sherpa-ONNX, offline)
- Runtime: `/root/.openclaw/tools/sherpa-onnx-tts/runtime`
- Envio via Evolution API (tj) → base64 → `sendWhatsAppAudio`
- **OpenAI-compatible TTS:** Gemini 2.5 Flash TTS configurado (aguarda restart para ativar)

### STT — Transcrição de áudio
- **Whisper local** (`openai-whisper`, modelo `small`) — funciona como workaround
- Deepgram nova-3 (PT-BR) é o pipeline nativo do OpenClaw — verificar se ativo
- Groq Whisper (`tools.media.audio`) não dispara — provider `groq` em `models.providers` corrige

### Novos contatos
- **S Vinícius** — +5521964407974 (Chefe SOE, recebe relatórios diários via cron 09:00 BRT)
- **G Charles** — +5521979330093 (chamar Eliandro de *Tjader*)
- **Rafael** — rafael@studiorr.com.br (Studio RR — FitFlow)

---

## FitFlow Suite — Contexto rápido (2026-04-13)

- Deploy: **fitflow-suite.vercel.app** — Rafael login: rafael@studiorr.com.br / StudioRR2024
- 3.875 alunos importados | 87 horários cadastrados (Seg-Sex 6h-21h, Sáb 6h-12h, Musculação, Recreio)
- **Booking API funcionando** — criar/cancelar OK | Rafael é ADMIN (fallback adicionado)
- **DATABASE_URL no Vercel:** usar `aws-0-us-west-2.pooler.supabase.com` (IPv4), não `db.` (IPv6)
- Laura = GLM-5.1 (único GLM com tool calling confiável — benchmark 12/04)
- **Teste Laura 12/04:** agendamento via WhatsApp funcionou, mas precisa perguntar modalidade quando aluno é vago
- **BigQuery:** dataset `fitflow` configurado — 4 tabelas; cron diário 00:30 BRT
- Workspace: `/root/projects/fitflow-suite`

### Pendências abertas
- [ ] **Criar slots pra Pilates, Personal, Funcional** (só Musculação tem horários)
- [ ] **Atualizar prompt Laura** — perguntar modalidade quando aluno não especificar
- [ ] **Stripe em produção** — hoje em modo teste
- [ ] **Supabase email confirmation** — desativar "Confirm email" (manual)
- [ ] **GOOGLE_APPLICATION_CREDENTIALS** no Vercel — BigQuery em produção
- [ ] **Evolution API key** — trocar "minha-chave-secreta" antes de produção
- [ ] **Rafael confirmar horários** + compartilhar planilha com service account
- [ ] **Apagar agendamentos de teste** quando terminar validação


---

## Estratégia Laura como produto

- Modelo: atendente IA white-label para PMEs (academias, clínicas, salões)
- Pricing recomendado: R$297-597/mês por unidade
- Margem bruta estimada: ~83% com 20 clientes
- **Fase 1 (0-10 clientes):** Evolution API + número do cliente (warmup feito)
- **Fase 2 (10-50):** Híbrido, iniciar migração WABA
- **Fase 3 (50-300):** WABA obrigatório — ban Meta é risco existencial em escala

### WABA futura — decisão documentada
- Usar **360dialog com Embedded Signup** — Eliandro vira parceiro ISV
- Custo realista: ~R$320/cliente/mês | Otimista (Laura reativa): ~R$128/cliente/mês
- Conversas iniciadas pelo cliente = gratuitas desde Nov/2024
- Infraestrutura: VPS 8GB (1º cliente) → 16GB (5 clientes) → 32GB (20 clientes)

---

## Fluxo de pesquisa — 3 níveis

| Nível | Quando | Modelos | Custo |
|---|---|---|---|
| Simples | Lookup pontual | Groq only | ~zero |
| Abrangente | Pesquisa com cobertura dupla | Groq + Gemini | ~zero |
| Estratégico | Decisão de negócio crítica | Groq + Gemini + Opus síntese | Opus ~$0.015/query |

Scout sinaliza `[ANÁLISE ESTRATÉGICA NECESSÁRIA]` quando Opus for justificado.
Opus reservado para: análise competitiva, decisões de infra, novo modelo de negócio.

---

## Convenções do workspace

### Context recovery
- **Ao iniciar sessão:** ler MEMORY.md + daily de hoje e ontem + STATE.md do projeto ativo
- **Ao finalizar tarefa grande:** atualizar STATE.md do projeto + MEMORY.md se algo estrutural mudar
- **MEMORY.md deve ser atualizado imediatamente quando algo de infra/estratégia mudar** — não esperar heartbeat

### Estrutura de projetos
```
workspace/
  projects/<nome>/STATE.md   ← estado atual, decisões, pendências
  memory/YYYY-MM-DD.md       ← log diário raw
  MEMORY.md                  ← este arquivo (índice curado)
/root/projects/<nome>/       ← código-fonte dos projetos
```

### Subagentes
- Todo subagente com tarefa significativa deve atualizar o STATE.md do projeto ao finalizar
- Instrução padrão: "Ao final, atualize `/root/.openclaw/workspace/projects/<nome>/STATE.md`"

---

## Lições aprendidas

- **2026-04-15:** Planilha Studio RR é .xlsx no Google Drive — acessar via Drive API + openpyxl. NUNCA usar Google Sheets API (erro 400). NUNCA dizer que não tem acesso. Registrado em TOOLS.md e SOUL.md da Laura.
- **2026-04-15:** Informação errada da Laura + meu erro de insistir que não tinha acesso à planilha causou constrangimento pro Eliandro. Sempre verificar com código ANTES de afirmar que algo não funciona. Dúvida → testa → confirma.
- **2026-04-15:** Painel professor = visualização + prescrição + observações. Check-in é SÓ admin. Professor NÃO agenda.
- **2026-03-25:** Sem STATE.md, tive que reconstruir contexto do zero — caro e lento. Nunca mais.
- **2026-03-25:** Modelo principal SEMPRE Anthropic (claude-sonnet). Nunca Grok — rate limit derruba WhatsApp.
- **2026-03-26:** Nunca mudar modelo primário sem aprovação explícita do Eliandro.
- **2026-03-26:** `openclaw gateway restart` via exec mata a sessão atual (SIGTERM) — pedir ao Eliandro rodar no terminal.
- **2026-03-28:** MEMORY.md ficou 3 dias desatualizado → esqueci instância `pessoal` configurada. Regra: atualizar sempre que algo estrutural mudar.
- **2026-04-12:** GLM-5.1 é o único modelo GLM com tool calling confiável. glm-5-turbo, glm-4.7, glm-4.5-air, glm-4.7-flash todos falharam em benchmarks. Laura migrada Haiku → GLM-5.1.
- **2026-04-14:** OpenAI (Tier 1, $100/mês) adicionada como 1º fallback em todos os agentes. Laura migrada GLM-5.1 → GPT-4.1-nano (custo 12x menor). Anthropic removido como primário do main e fitflow (rate limits). Z.AI agora é primário de main/fitflow com OpenAI como fallback pago.
- **2026-03-29:** WhatsApp status 499 (reconexão): esperado — app mobile sendo suspenso pelo SO. Não é falha de servidor.
- **2026-04-03:** Google Cloud credits (R$1.759) NÃO cobrem API Gemini — são créditos GCP distintos. R$192 cobrados. NUNCA usar Google/Gemini como modelo de IA. Anthropic + Groq apenas.
- **2026-04-03:** Fallback do agente `main` estava como `"gemini 3.1 pro"` (sem provider prefix) → OpenClaw tentava `anthropic/gemini 3.1 pro` → falha total. Corrigido para `"google/gemini-2.5-pro-preview"` no `/root/.openclaw/openclaw.json`.
- **2026-03-30:** Status 499 no OpenClaw = heartbeat interno — reconecta automaticamente quando não recebe mensagens por ~60-80min. Normal. Status 401 = sessão invalidada (problema real) — causa: reconectar instância `tj` na Evolution derruba a sessão do OpenClaw (mesmo número). Solução: `openclaw channels login` + não mexer na instância `tj` desnecessariamente.
- Subagentes têm histórico isolado — contexto não chega automaticamente; precisam escrever arquivos.
- **2026-03-31:** Gemini 2.5 Flash aprovado como fallback para conversas (qualidade aceitável para não-código). Influencie rodando em Gemini 3 Flash — conteúdo criativo não precisa de Sonnet.
- **2026-03-31:** Múltiplas contas Rise aprovadas — estratégia de expandir canais para maximizar alcance e monetização. Workspace-influencie criado em `/root/.openclaw/workspace-influencie/`.
- **2026-04-01:** Instagram Basic Display API foi descontinuada em dez/2024. Usar sempre "Instagram API with Instagram Login" — sem necessidade de Facebook Page. **Lição crítica:** testar API antes de assumir que funciona.
- **2026-04-04:** Monitor agente eliminado — 100% falha por rate limit Groq, 40K-231K tokens/run sem valor real, foi causa do estouro de créditos Google. Scout reformulado com prompt cirúrgico.
- **2026-04-05:** Estrutura de fallback tripla (Sonnet → GLM → Groq) implementada após queda dupla de Anthropic + Groq. Garante alta disponibilidade.
- **2026-04-06:** SOE Clone (`soe-groq`) nunca deve enviar pro Vinícius nem pedir confirmação de envio — existe só pra comparação de qualidade. Quem envia é o `soe` (principal), sem aprovação.
- **2026-04-05:** `historyLimit` controla apenas o histórico do JSONL da sessão, NÃO o histórico pendente injetado no system prompt. Para grupos com muita atividade, o contexto pendente pode ser enorme — risco de 413 Request too large.
- **2026-04-05:** Heartbug fix: Heartbeat NÃO deve retomar tarefas que estavam aguardando confirmação do usuário. Se uma tarefa ficou pendente de confirmação e o usuário não respondeu, ela é descartada — nunca executada automaticamente.
