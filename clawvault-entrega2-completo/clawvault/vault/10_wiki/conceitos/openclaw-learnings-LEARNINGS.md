---
title: Lições OpenClaw (LEARNINGS)
created: 2026-04-25 02:47
source: openclaw/learnings
layer: wiki
tags: [openclaw, licoes, sincronizado]
---

# Lições: LEARNINGS

# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260421-001] best_practice

**Logged**: 2026-04-21T09:36:00Z
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
`openclaw models --agent <id> set/fallbacks` did not behave as a safe per-agent model override for this setup; the reliable per-agent path is `agents.list[].model` in `openclaw.json`.

### Details
While configuring `main`, `laura`, and `fitflow`, the CLI `models --agent` commands updated `~/.openclaw/openclaw.json` global defaults instead of producing the intended final per-agent state. The config schema confirms per-agent overrides belong in `agents.list[].model`, which accepts either a string or `{ primary, fallbacks }`.

### Suggested Action
For future multi-agent model changes, edit or set `agents.list[].model` directly and validate with `openclaw config validate` before considering the task complete.

### Metadata
- Source: error
- Related Files: /root/.openclaw/openclaw.json
- Tags: openclaw, models, multi-agent, config

---

## [LRN-20260423-001] best_practice

**Logged**: 2026-04-23T14:12:00Z
**Priority**: critical
**Status**: resolved
**Area**: infra

### Summary
Whisper local (3.4GB RAM) causa OOM kill em servidor com 3.7GB RAM. Usar Deepgram API.

### Details
Áudios WhatsApp eram transcritos por Whisper local que consumia 3.4GB RAM. Servidor tem 3.7GB total. OOM killer do Linux matava o gateway inteiro a cada áudio recebido. Solução: Deepgram nova-3 via API (zero RAM local).

### Metadata
- Source: error
- Related Files: openclaw.json (tools.media.models)
- Tags: audio, whisper, oom, deepgram, memory

---

## [LRN-20260423-002] best_practice

**Logged**: 2026-04-23T14:12:00Z
**Priority**: critical
**Status**: resolved
**Area**: config

### Summary
NUNCA usar valores absurdos em heartbeat.every — causa integer overflow e flood de timers.

### Details
Configurar `heartbeat.every: "10000h"` causou TimeoutOverflowWarning no Node.js (266K+ warnings em 15min). O timer colapsou pra 1ms e engasgou o gateway. Pra desativar heartbeat, usar `heartbeat: {}` (objeto vazio).

### Metadata
- Source: error
- Tags: heartbeat, overflow, config, timer

---
