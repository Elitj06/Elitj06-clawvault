---
title: Projeto clawvault (OpenClaw)
created: 2026-04-25 02:47
source: openclaw/project
layer: wiki
tags: [openclaw, projeto, clawvault, sincronizado]
---

# Projeto: clawvault

# ClawVault — STATE.md

## Última atualização: 2025-04-25

## Feito (Entrega 2)
- ✅ **Vault search no system prompt** — backend busca notas relevantes (`vault.search`) antes de montar o prompt e injeta contexto automaticamente
- ✅ **Histórico de conversas no sidebar** — lista 10 conversas recentes com título e data, clicável para carregar mensagens
- ✅ **Alternar entre sessões** — clicar em conversa no sidebar navega para `/chat` e carrega mensagens anteriores
- ✅ **Cursor ativo após Enter** — textarea recebe focus após enviar e ao carregar a página
- ✅ **Toggle dark/light mode** — botão Sol/Lua no sidebar, persiste em localStorage, anti-flash script no layout
- ✅ **Dark mode CSS** — `.card`, `.btn-primary`, `.btn-secondary`, `.nav-link-active`, `.input` com estilos dark via Tailwind `dark:` prefix
- ✅ **Build passando** — `npm run build` sem erros

## Arquivos modificados/criados
1. `backend/api/server.py` — vault search no system prompt (chat endpoint)
2. `frontend/src/components/Sidebar.tsx` — histórico + theme toggle + exports para comunicação
3. `frontend/src/app/chat/page.tsx` — cursor fix + loadConversation + dark classes
4. `frontend/src/components/ThemeToggle.tsx` — NOVO componente
5. `frontend/src/app/globals.css` — dark mode styles para todos componentes
6. `frontend/src/app/layout.tsx` — anti-flash script + dark body classes

## Pendências
- [ ] Testar fluxo completo com backend rodando
- [ ] Verificar se vault.search retorna campos `title` e `snippet` corretamente
