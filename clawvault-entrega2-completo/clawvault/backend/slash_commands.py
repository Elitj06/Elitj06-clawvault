"""
ClawVault - Slash Commands
==========================

Sistema de comandos curtos que economizam toques do usuário.

Sintaxe: a primeira palavra da mensagem começa com "/" e dispara um
comando estruturado em vez de uma chamada normal ao LLM.

Exemplos:
    /vault search supabase     → busca no vault, sem LLM
    /agent code "fix bug X"    → roteia pro agente "code"
    /recall ontem              → recupera última conversa de ontem
    /summary semana            → resumo das últimas 7 dias
    /cost                      → mostra gasto atual
    /forget X                  → marca fato/nota como deprecated
    /playbook list             → lista playbooks (futuro P-)
    /help                      → lista todos os comandos

Vantagem: comandos comuns viram zero-toques + zero-token (não chamam LLM).
"""

import re
from datetime import datetime, timedelta
from typing import Any, Optional

from backend.core.database import db, get_monthly_spend
from backend.memory.vault import vault
from backend.memory.multi_agent import AgentRegistry, get_agent_memory
from backend.observability import metrics


# ==========================================================================
# REGISTRO DE COMANDOS
# ==========================================================================

class CommandResult:
    """Resultado de um comando."""

    def __init__(
        self,
        success: bool,
        message: str,
        data: Any = None,
        used_llm: bool = False,
    ):
        self.success = success
        self.message = message
        self.data = data
        self.used_llm = used_llm

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "used_llm": self.used_llm,
            "is_command": True,
        }


# ==========================================================================
# IMPLEMENTAÇÕES
# ==========================================================================

def _cmd_help(_args: str) -> CommandResult:
    help_text = (
        "**Comandos disponíveis:**\n\n"
        "**Vault & Conhecimento**\n"
        "  `/vault search <termo>` — busca notas no vault\n"
        "  `/vault entities` — lista entidades conhecidas (pessoas, projetos…)\n"
        "  `/vault stats` — estatísticas do vault\n\n"
        "**Memória & Histórico**\n"
        "  `/recall ontem|semana|mes` — recupera conversas recentes\n"
        "  `/summary [periodo]` — resumo de uso\n"
        "  `/forget <termo>` — marca notas com termo como deprecated\n\n"
        "**Agentes**\n"
        "  `/agent list` — lista todos os agentes\n"
        "  `/agent <nome> <mensagem>` — fala com agente específico\n\n"
        "**Sistema**\n"
        "  `/cost` — gasto do mês atual\n"
        "  `/cache` — métricas de cache\n"
        "  `/status` — status geral do sistema\n"
        "  `/help` — esta lista"
    )
    return CommandResult(True, help_text)


def _cmd_vault(args: str) -> CommandResult:
    parts = args.strip().split(maxsplit=1)
    if not parts:
        return CommandResult(
            False,
            "Uso: `/vault search <termo>` | `/vault entities` | `/vault stats`",
        )

    sub = parts[0].lower()

    if sub == "search":
        if len(parts) < 2:
            return CommandResult(False, "Uso: `/vault search <termo>`")
        query = parts[1]
        results = vault.search(query, limit=8)
        if not results:
            return CommandResult(True, f"Nenhuma nota encontrada para `{query}`.")

        lines = [f"**Encontrei {len(results)} nota(s) para `{query}`:**\n"]
        for r in results:
            snippet = r["snippet"][:120].strip()
            lines.append(f"- **{r['path']}** ({r['layer']})\n  > {snippet}…")
        return CommandResult(True, "\n".join(lines), data={"results": results})

    if sub == "entities":
        ents = vault.list_entities()
        lines = ["**Entidades no vault:**\n"]
        for cat, names in ents.items():
            if names:
                lines.append(f"- **{cat}** ({len(names)}): {', '.join(names[:10])}"
                             + (f" … +{len(names) - 10}" if len(names) > 10 else ""))
        if len(lines) == 1:
            return CommandResult(True, "Nenhuma entidade ainda no vault.")
        return CommandResult(True, "\n".join(lines), data={"entities": ents})

    if sub == "stats":
        from backend.memory.vault import VAULT_STRUCTURE
        from backend.core.config import VAULT_DIR
        from pathlib import Path

        result = []
        total = 0
        for label, folder in VAULT_STRUCTURE.items():
            path = VAULT_DIR / folder
            if path.exists():
                files = list(path.rglob("*.md"))
                if files:
                    total += len(files)
                    result.append(f"- **{label}**: {len(files)} notas")

        msg = f"**Vault: {total} notas no total**\n\n" + "\n".join(result)
        return CommandResult(True, msg)

    return CommandResult(False, f"Subcomando `{sub}` desconhecido. Veja `/help`.")


def _cmd_recall(args: str) -> CommandResult:
    """Recupera conversas recentes."""
    period = (args.strip().lower() or "ontem")
    now = datetime.now()

    if period == "hoje":
        since = now.replace(hour=0, minute=0, second=0).isoformat()
        label = "hoje"
    elif period == "ontem":
        since = (now - timedelta(days=1)).replace(hour=0, minute=0).isoformat()
        until = now.replace(hour=0, minute=0).isoformat()
        rows = db.fetch_all(
            """
            SELECT id, uuid, title, agent_name, created_at, total_tokens, total_cost_usd
            FROM conversations
            WHERE created_at >= ? AND created_at < ?
            ORDER BY created_at DESC LIMIT 10
            """,
            (since, until),
        )
        if not rows:
            return CommandResult(True, "Nenhuma conversa de ontem.")
        lines = ["**Conversas de ontem:**\n"]
        for r in rows:
            lines.append(f"- #{r['id']} **{r['title'] or 'sem título'}** "
                         f"({r['agent_name']}) — {r['total_tokens']} tokens · "
                         f"${r['total_cost_usd']:.4f}")
        return CommandResult(True, "\n".join(lines), data={"conversations": rows})
    elif period == "semana":
        since = (now - timedelta(days=7)).isoformat()
        label = "última semana"
    elif period == "mes" or period == "mês":
        since = (now - timedelta(days=30)).isoformat()
        label = "último mês"
    else:
        return CommandResult(False, "Uso: `/recall hoje|ontem|semana|mes`")

    rows = db.fetch_all(
        """
        SELECT id, uuid, title, agent_name, created_at, total_tokens, total_cost_usd
        FROM conversations
        WHERE created_at >= ?
        ORDER BY created_at DESC LIMIT 15
        """,
        (since,),
    )
    if not rows:
        return CommandResult(True, f"Nenhuma conversa nas/no {label}.")

    lines = [f"**Conversas {label}:**\n"]
    for r in rows:
        lines.append(f"- #{r['id']} **{r['title'] or 'sem título'}** "
                     f"({r['agent_name']}) — {r['created_at'][:10]}")
    return CommandResult(True, "\n".join(lines), data={"conversations": rows})


def _cmd_summary(args: str) -> CommandResult:
    period = args.strip().lower() or "semana"
    days_map = {"hoje": 1, "ontem": 2, "semana": 7, "mes": 30, "mês": 30}
    days = days_map.get(period, 7)

    ov = metrics.overview(days=days)

    lines = [
        f"**Resumo dos últimos {days} dias:**",
        "",
        f"- **{ov['calls']}** chamadas (sucesso: {ov['success']/max(ov['calls'],1)*100:.0f}%)",
        f"- **${ov['cost_usd']:.4f}** gastos (${ov['cost_per_day_usd']:.4f}/dia)",
        f"- **{ov['tokens']['total']:,}** tokens totais",
    ]
    if ov['cache_hit_rate'] > 0:
        lines.append(f"- **{ov['cache_hit_rate']*100:.1f}%** cache hit rate "
                     f"(economia: ${ov['cost_saved_usd']:.4f})")
    return CommandResult(True, "\n".join(lines), data=ov)


def _cmd_cost(_args: str) -> CommandResult:
    spend = get_monthly_spend()
    pct = (spend["spent_usd"] / spend["budget_usd"]) * 100 if spend["budget_usd"] else 0

    msg = (
        f"**Gasto do mês ({spend['year_month']}):**\n\n"
        f"- Gasto: **${spend['spent_usd']:.4f}**\n"
        f"- Orçamento: **${spend['budget_usd']:.2f}**\n"
        f"- Usado: **{pct:.2f}%**\n"
    )

    if pct > 80:
        msg += "\n⚠️ Alerta: você passou de 80% do orçamento mensal."
    elif pct > 50:
        msg += "\n💡 Atenção: meio do orçamento mensal já consumido."

    return CommandResult(True, msg, data=spend)


def _cmd_cache(_args: str) -> CommandResult:
    cm = metrics.cache_metrics(days=7)
    msg = (
        "**Cache (últimos 7 dias):**\n\n"
        f"- Hit rate: **{cm['hit_rate']*100:.1f}%**\n"
        f"- Tokens cacheados: **{cm['cached_tokens']:,}** de {cm['input_tokens']:,}\n"
        f"- Economizado (estimativa): **${cm['cost_saved_estimate_usd']:.4f}**\n"
    )
    return CommandResult(True, msg, data=cm)


def _cmd_status(_args: str) -> CommandResult:
    """Status geral: providers ativos + budget + stats."""
    from backend.core.config import API_KEYS

    providers = {
        "anthropic": bool(API_KEYS.anthropic),
        "openai": bool(API_KEYS.openai),
        "groq": bool(API_KEYS.groq),
        "openrouter": bool(API_KEYS.openrouter),
        "google": bool(API_KEYS.google),
    }
    active = [p for p, v in providers.items() if v]

    spend = get_monthly_spend()

    conv_count = db.fetch_one("SELECT COUNT(*) as n FROM conversations")
    msg_count  = db.fetch_one("SELECT COUNT(*) as n FROM messages")

    msg = (
        "**Status do ClawVault:**\n\n"
        f"- Providers ativos: **{', '.join(active) or 'nenhum'}**\n"
        f"- Conversas: **{conv_count['n']}**\n"
        f"- Mensagens: **{msg_count['n']}**\n"
        f"- Gasto mês: **${spend['spent_usd']:.4f}** / ${spend['budget_usd']:.2f}\n"
    )
    return CommandResult(True, msg)


def _cmd_agent(args: str) -> CommandResult:
    parts = args.strip().split(maxsplit=1)
    if not parts:
        return CommandResult(False, "Uso: `/agent list` ou `/agent <nome> <mensagem>`")

    if parts[0].lower() == "list":
        agents = AgentRegistry.list_all()
        if not agents:
            return CommandResult(True, "Nenhum agente cadastrado.")
        lines = ["**Agentes:**\n"]
        for a in agents:
            star = "★ " if a.get("is_main") else "  "
            lines.append(f"- {star}**{a['name']}** — {a.get('role') or 'sem descrição'}")
        return CommandResult(True, "\n".join(lines), data={"agents": agents})

    # /agent <nome> <mensagem> — sinaliza pra UI rotear pro agente certo
    return CommandResult(
        True,
        f"_(rotear próxima mensagem pro agente `{parts[0]}`)_",
        data={"route_to_agent": parts[0], "next_message": parts[1] if len(parts) > 1 else ""},
    )


def _cmd_forget(args: str) -> CommandResult:
    """Marca notas que contêm o termo como deprecated."""
    term = args.strip()
    if not term:
        return CommandResult(False, "Uso: `/forget <termo>`")

    results = vault.search(term, limit=20)
    if not results:
        return CommandResult(True, f"Nenhuma nota contém `{term}` — nada para esquecer.")

    return CommandResult(
        True,
        f"Encontrei {len(results)} nota(s) com `{term}`. Para confirmar a marcação como "
        f"deprecated, responda: `confirmar forget {term}`",
        data={"pending_forget": term, "matches": results},
    )


# ==========================================================================
# REGISTRY
# ==========================================================================

COMMANDS = {
    "help":    _cmd_help,
    "vault":   _cmd_vault,
    "recall":  _cmd_recall,
    "summary": _cmd_summary,
    "cost":    _cmd_cost,
    "cache":   _cmd_cache,
    "status":  _cmd_status,
    "agent":   _cmd_agent,
    "forget":  _cmd_forget,
}


# ==========================================================================
# DETECÇÃO E EXECUÇÃO
# ==========================================================================

SLASH_RE = re.compile(r"^/(\w+)\b\s*(.*)$", re.DOTALL)


def is_slash_command(message: str) -> bool:
    """Retorna True se a mensagem começa com /comando."""
    if not message or not message.startswith("/"):
        return False
    m = SLASH_RE.match(message.strip())
    return bool(m and m.group(1).lower() in COMMANDS)


def execute_slash_command(message: str) -> Optional[CommandResult]:
    """
    Executa um slash command. Retorna None se a mensagem não é um comando.
    """
    if not message.startswith("/"):
        return None
    m = SLASH_RE.match(message.strip())
    if not m:
        return None
    cmd_name = m.group(1).lower()
    args = m.group(2) or ""

    handler = COMMANDS.get(cmd_name)
    if not handler:
        return CommandResult(
            False,
            f"Comando `/{cmd_name}` não existe. Tente `/help`.",
        )

    try:
        return handler(args)
    except Exception as e:
        return CommandResult(
            False,
            f"Erro ao executar `/{cmd_name}`: {e}",
        )


def list_commands() -> list[str]:
    """Lista nomes dos comandos disponíveis (para autocomplete na UI)."""
    return sorted(COMMANDS.keys())
