---
title: Projeto compras-coletivas (OpenClaw)
created: 2026-04-25 02:47
source: openclaw/project
layer: wiki
tags: [openclaw, projeto, compras-coletivas, sincronizado]
---

# Projeto: compras-coletivas

# STATE.md — Compras Coletivas

> Última atualização: 2026-04-08 11:25 UTC

## Status atual
🔧 **Em correção** — API offline no Vercel, migrando para `@vercel/postgres`

## O que é
Sistema de compras coletivas para a Vida Forte (igreja). Membros fazem pedidos de produtos, admin consolida e compra em grupo.

## Deploy
- **URL:** compras-coletivas-phi.vercel.app
- **Repo:** (definir)
- **Banco:** Supabase (schema `compras_coletivas`)

## Problema atual (2026-04-08)
- **Causa:** `postgres` (node-postgres) usa TCP porta 5432 → **não funciona em Edge Runtime**
- **Solução:** Migrado para `@vercel/postgres` (WebSocket/HTTP)

## ⚠️ Ação necessária no Vercel
Configurar estas env vars no dashboard do Vercel:

```
POSTGRES_URL=postgresql://postgres.vpmfuhvgnbqovclwaudz:[SENHA]@aws-0-us-west-2.pooler.supabase.com:5432/postgres?pgbouncer=true&options=--search_path%3Dcompras_coletivas
```

**OU** usar as vars do Supabase Connection Pooling:
- `POSTGRES_HOST=aws-0-us-west-2.pooler.supabase.com`
- `POSTGRES_USER=postgres.vpmfuhvgnbqovclwaudz`
- `POSTGRES_PASSWORD=[SENHA]`
- `POSTGRES_DATABASE=postgres`

> ⚠️ **Importante:** Usar o **Connection Pooler** (Supavisor), não a conexão direta

## Próximos passos
- [ ] Deploy da correção
- [ ] Testar login admin
- [ ] Validar endpoints

## Arquitetura
- Frontend: HTML/CSS/JS estático
- API: `/api/db.js` (Edge Runtime)
- Banco: Supabase PostgreSQL (schema isolado)

## Pendências
- [ ] Mover senha admin para env var
- [ ] Implementar autenticação real (JWT)
- [ ] Backup automático do banco
