---
title: Projeto fitflow-suite (OpenClaw)
created: 2026-04-25 02:47
source: openclaw/project
layer: wiki
tags: [openclaw, projeto, fitflow-suite, sincronizado]
---

# Projeto: fitflow-suite

# FitFlow Suite — STATE.md

## Último commit: `2d6b8a44` (2026-04-22)
**feat(api): 5 novos endpoints v1**

### Endpoints implementados
1. **GET /api/v1/students** — modificado: sem params retorna todos os alunos ativos (com paginação limit/offset). Com search/phone mantém busca existente (limit 10).
2. **GET /api/v1/prescriptions** — novo: histórico de prescrições por studentId, filtro opcional por active
3. **GET /api/v1/reports/attendance** — novo: presenças, faltas, cancelamentos com breakdown diário e por aluno
4. **GET /api/v1/reports/cancellations** — novo: análise de cancelamentos com motivos, por dia/aluno/professor
5. **GET /api/v1/reports/students** — novo: total ativos, novos no período, source breakdown, top 10 por bookings, aggregators

### Arquivos criados/modificados
- `web/src/app/api/v1/students/route.ts` (modificado)
- `web/src/app/api/v1/prescriptions/route.ts` (novo)
- `web/src/app/api/v1/reports/attendance/route.ts` (novo)
- `web/src/app/api/v1/reports/cancellations/route.ts` (novo)
- `web/src/app/api/v1/reports/students/route.ts` (novo)

### Status
- Build ✅ | Push para main ✅ | Vercel deploy automático em andamento
- FITFLOW_API.md da Laura atualizado com os 5 endpoints

---

## Commit anterior: `6c6796ec` (2026-04-16)
**Fix: Cadastro de professores — userId com UUID**

### Bug corrigido
- **Problema:** POST `/api/admin/trainers` usava `manual_${Date.now()}` como `userId`. O campo `userId` tem `@unique` — `Date.now()` pode colidir em chamadas rápidas e não é um formato confiável.
- **Correção:** Substituído por `crypto.randomUUID()` — UUID v4 padrão, sem risco de colisão.
- **Arquivo:** `web/src/app/api/admin/trainers/route.ts` (linha do `prisma.profile.create`)
- Build ✅ | Push para main ✅

### Pendências
- Aguardar deploy do Vercel e testar endpoints com curl
