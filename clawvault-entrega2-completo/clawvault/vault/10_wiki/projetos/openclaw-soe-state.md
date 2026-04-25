---
title: Projeto soe (OpenClaw)
created: 2026-04-25 02:47
source: openclaw/project
layer: wiki
tags: [openclaw, projeto, soe, sincronizado]
---

# Projeto: soe

# SOE — Relatórios Automáticos
## Estado do Projeto — Atualizado em 05/04/2026 14:10 BRT

---

## JIDs dos Grupos

| Grupo | JID |
|---|---|
| Chefia de Base (serviços) | `5521964409345-1514984626@g.us` |
| Planejamento (frota) | `5521964407974-1542754285@g.us` |

---

## Instâncias Evolution API

- **Leitura:** instância `orion`
- **Envio:** instância `tj`
- **URL:** `http://localhost:8080`

---

## Relatório de Hoje (05/04/2026)

### Data dos Dados Usados
- **Serviços:** 04/04/2026 (sábado) — dados parciais, domingo com menor volume de reporte
- **Frota:** 05/04/2026 (domingo) — dados atualizados dos grupos

### Observações dos Dados
- Apenas 3 bases com reporte de serviços: SEVR (16 audiências CEAC), SEEC (14 audiências custódia), SEEN (zerinho)
- SEEJ, SECSEGR, SEEI, SEEG — sem reporte até 14h BRT (domingo)
- SEEI enviou formulário em branco para 05/04 — tratado como sem reporte
- Frota: VTR 06-2586 (Campos) baixada; VTR 06-2599 (Niterói) avaria persistente (3º dia)

### PDFs Gerados (válidos por 72h — catbox.moe)
| Relatório | URL |
|---|---|
| Briefing Tático (Serviços) | https://litter.catbox.moe/14pa6k.pdf |
| Frota de Viaturas | https://litter.catbox.moe/ozttpw.pdf |

### Envio
- **Destinatário:** Vinícius (+5521964407974)
- **Status:** ✅ ENVIADO — `messageId: 3EB0277B2864BBCD6A7C08`
- **Horário:** 05/04/2026 ~14:10 BRT
- **Nota:** Catbox.moe principal indisponível — usado litterbox (72h TTL)

---

## Scripts

| Arquivo | Função |
|---|---|
| `run_daily.sh` | Script principal — gera, faz upload (catbox → litterbox fallback) e envia |
| `extrair_dados.py` | Extrai dados dos grupos + salva JSON em `data/YYYY/MM/` automaticamente |
| `gerar_relatorio_servicos.py` | Gera briefing tático |
| `gerar_relatorio_frota.py` | Gera relatório de frota |
| `consolidar.py` | Consolida histórico (semanal/mensal/anual/range) — Python puro, zero tokens de IA |
| `dados_exemplo.py` | Dados de fallback |
| `dados_DDMMYYYY.py` | Backup Python por dia (legado) |
| `data/YYYY/MM/dados_DDMMYYYY.json` | **Histórico estruturado** — gerado automaticamente a cada run |

## Fluxo de Dados

1. Buscar mensagens dos dois grupos (instância `orion`)
2. Extrair: serviços do grupo Chefia de Base, frota do grupo Planejamento
3. Criar `dados_DDMMYYYY.py` com dados do dia
4. Copiar para `dados_exemplo.py` (arquivo ativo)
5. Rodar `job_relatorios_hoje.py`
6. Upload para litterbox/catbox
7. Enviar links para Vinícius (+5521964407974) via instância `tj`

---

## Regras de envio (IMPORTANTE — não esquecer)

| Cron | Agente | Comportamento correto |
|---|---|---|
| SOE — Relatório Diário 09h | `soe` | Gera + ENVIA diretamente pra Vinícius. Sem aprovação. Sem confirmação. |
| SOE Clone — Relatório Diário (sem envio) | `soe-groq` | Gera APENAS para comparação de qualidade. Entrega URLs ao Eliandro. NUNCA envia pro Vinícius. NUNCA pede confirmação de envio. |

**Falha de 05/04/2026:** Clone rodou e entregou ao Eliandro mas perguntou "Confirma envio?". Isso é ERRADO. Corrigido no prompt do cron em 06/04/2026.

---

## Histórico de Execuções

| Data | Status | Arquivo de Dados | Observação |
|---|---|---|---|
| 04/04/2026 | ✅ Enviado | dados_04042026.py | Dados ref. 03/04 — SEEC e SEEG sem reporte |
| 05/04/2026 | ✅ Enviado | dados_05042026.py | Dados parciais — domingo | Litterbox 72h (catbox principal indisponível) |
