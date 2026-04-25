"""
ClawVault - Observability
=========================

Módulo de observabilidade avançada. Fornece métricas agregadas a partir
da tabela `usage_log` que JÁ EXISTE no `database.py`. Não cria tabelas
novas — só consulta o que já temos com queries inteligentes.

Endpoints expostos via API server:
  GET /api/observability/overview     — visão geral (custo/dia, latência, fallbacks)
  GET /api/observability/by-model     — quebra por modelo
  GET /api/observability/by-agent     — quebra por agente
  GET /api/observability/cache        — métricas do cache (hit rate, tokens economizados)
  GET /api/observability/timeline     — série temporal últimos N dias

Uso interno também: `from backend.observability import metrics`
"""

from datetime import datetime, timedelta
from typing import Optional

from backend.core.database import db


# ==========================================================================
# CLASSE PRINCIPAL
# ==========================================================================

class Observability:
    """Coleta e agrega métricas de uso do ClawVault."""

    # ----------------------------------------------------------------------
    # Visão geral
    # ----------------------------------------------------------------------

    def overview(self, days: int = 7) -> dict:
        """
        Retorna visão geral dos últimos N dias.

        Inclui:
          - Custo total e por dia
          - Total de chamadas e taxa de sucesso
          - Tokens (input/output/cached)
          - Cache hit rate (% de tokens que vieram do cache vs total)
          - Latência (TODO: quando adicionarmos coluna)
          - Top fallbacks (qual modelo quebra mais)
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()

        totals = db.fetch_one(
            """
            SELECT
                COUNT(*) AS calls,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS success,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS errors,
                COALESCE(SUM(input_tokens), 0)  AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                COALESCE(SUM(cost_usd), 0.0)    AS cost_usd
            FROM usage_log
            WHERE timestamp >= ?
            """,
            (since,),
        ) or {}

        calls         = totals.get("calls") or 0
        success       = totals.get("success") or 0
        errors        = totals.get("errors") or 0
        input_tokens  = totals.get("input_tokens") or 0
        cached_tokens = totals.get("cached_tokens") or 0

        # Cache hit rate (% dos tokens de input que vieram do cache)
        cache_rate = (cached_tokens / input_tokens) if input_tokens > 0 else 0.0

        # Custo SEM cache (estimativa do que teria gasto sem otimização)
        # cached_tokens custou ~10% do normal — estimo o "salvo" como 90%
        # do que esses tokens custariam (média de input cost ponderada)
        cost_saved_estimate = self._estimate_cost_saved(since)

        return {
            "period_days": days,
            "since": since,
            "calls":       calls,
            "success":     success,
            "errors":      errors,
            "success_rate": (success / calls) if calls > 0 else 1.0,
            "tokens": {
                "input":  input_tokens,
                "output": totals.get("output_tokens") or 0,
                "cached": cached_tokens,
                "total":  input_tokens + (totals.get("output_tokens") or 0),
            },
            "cache_hit_rate": round(cache_rate, 4),
            "cost_usd":         round(totals.get("cost_usd") or 0.0, 6),
            "cost_saved_usd":   round(cost_saved_estimate, 6),
            "cost_per_day_usd": round((totals.get("cost_usd") or 0.0) / max(days, 1), 6),
        }

    # ----------------------------------------------------------------------
    # Quebra por modelo
    # ----------------------------------------------------------------------

    def by_model(self, days: int = 7) -> list[dict]:
        """Custo, calls e taxa de sucesso por modelo nos últimos N dias."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = db.fetch_all(
            """
            SELECT
                model_id,
                provider,
                COUNT(*) AS calls,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS success,
                COALESCE(SUM(input_tokens), 0)  AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                COALESCE(SUM(cost_usd), 0.0)    AS cost_usd
            FROM usage_log
            WHERE timestamp >= ?
            GROUP BY model_id, provider
            ORDER BY cost_usd DESC, calls DESC
            """,
            (since,),
        )
        # Adiciona success_rate calculada
        for r in rows:
            r["success_rate"] = (r["success"] / r["calls"]) if r["calls"] else 1.0
            r["cost_usd"] = round(r["cost_usd"], 6)
        return rows

    # ----------------------------------------------------------------------
    # Quebra por agente
    # ----------------------------------------------------------------------

    def by_agent(self, days: int = 7) -> list[dict]:
        """Custo e calls por agente, juntando via conversation_id."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = db.fetch_all(
            """
            SELECT
                COALESCE(c.agent_name, 'desconhecido') AS agent_name,
                COUNT(u.id) AS calls,
                COALESCE(SUM(u.input_tokens), 0)  AS input_tokens,
                COALESCE(SUM(u.output_tokens), 0) AS output_tokens,
                COALESCE(SUM(u.cached_tokens), 0) AS cached_tokens,
                COALESCE(SUM(u.cost_usd), 0.0)    AS cost_usd
            FROM usage_log u
            LEFT JOIN conversations c ON c.id = u.conversation_id
            WHERE u.timestamp >= ?
            GROUP BY agent_name
            ORDER BY cost_usd DESC
            """,
            (since,),
        )
        for r in rows:
            r["cost_usd"] = round(r["cost_usd"], 6)
        return rows

    # ----------------------------------------------------------------------
    # Métricas de cache
    # ----------------------------------------------------------------------

    def cache_metrics(self, days: int = 7) -> dict:
        """
        Métricas do prompt caching (Anthropic/OpenAI).

        - hit_rate: % dos tokens de input que vieram do cache
        - tokens_saved: estimativa de tokens cacheados
        - cost_saved: estimativa de USD economizados via cache
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()
        row = db.fetch_one(
            """
            SELECT
                COALESCE(SUM(input_tokens), 0)  AS input_tokens,
                COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                COALESCE(SUM(cost_usd), 0.0)    AS cost_actual
            FROM usage_log
            WHERE timestamp >= ? AND success = 1
            """,
            (since,),
        ) or {}

        input_tokens  = row.get("input_tokens") or 0
        cached_tokens = row.get("cached_tokens") or 0

        hit_rate = (cached_tokens / input_tokens) if input_tokens > 0 else 0.0
        cost_saved = self._estimate_cost_saved(since)

        return {
            "period_days":    days,
            "input_tokens":   input_tokens,
            "cached_tokens":  cached_tokens,
            "hit_rate":       round(hit_rate, 4),
            "cost_actual_usd": round(row.get("cost_actual") or 0.0, 6),
            "cost_saved_estimate_usd": round(cost_saved, 6),
        }

    # ----------------------------------------------------------------------
    # Timeline (série temporal)
    # ----------------------------------------------------------------------

    def timeline(self, days: int = 30, granularity: str = "day") -> list[dict]:
        """
        Série temporal de custo e calls por dia (ou hora).
        Útil pro gráfico do dashboard.
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()
        if granularity == "hour":
            time_format = "%Y-%m-%d %H:00"
        else:
            time_format = "%Y-%m-%d"

        rows = db.fetch_all(
            f"""
            SELECT
                strftime('{time_format}', timestamp) AS bucket,
                COUNT(*) AS calls,
                COALESCE(SUM(input_tokens),  0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                COALESCE(SUM(cost_usd),    0.0) AS cost_usd
            FROM usage_log
            WHERE timestamp >= ?
            GROUP BY bucket
            ORDER BY bucket ASC
            """,
            (since,),
        )
        for r in rows:
            r["cost_usd"] = round(r["cost_usd"], 6)
        return rows

    # ----------------------------------------------------------------------
    # Top consumidores
    # ----------------------------------------------------------------------

    def top_conversations(self, limit: int = 10) -> list[dict]:
        """Conversas mais caras (último mês)."""
        since = (datetime.now() - timedelta(days=30)).isoformat()
        return db.fetch_all(
            """
            SELECT
                c.id, c.uuid, c.title, c.agent_name,
                c.total_tokens, c.total_cost_usd, c.created_at
            FROM conversations c
            WHERE c.created_at >= ?
            ORDER BY c.total_cost_usd DESC
            LIMIT ?
            """,
            (since, limit),
        )

    # ----------------------------------------------------------------------
    # Helpers internos
    # ----------------------------------------------------------------------

    def _estimate_cost_saved(self, since: str) -> float:
        """
        Estima quanto teria sido gasto SEM o cache hit.
        Multiplica cached_tokens pelo cost_input médio (ponderado por uso),
        depois aplica o desconto de cache (10% Anthropic, 50% OpenAI — média 25%).
        """
        rows = db.fetch_all(
            """
            SELECT
                provider,
                COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(cost_usd), 0.0) AS cost
            FROM usage_log
            WHERE timestamp >= ? AND cached_tokens > 0
            GROUP BY provider
            """,
            (since,),
        )
        # Estimativa simples: assume Anthropic-like 90% saving
        total_saved = 0.0
        for r in rows:
            cached = r.get("cached_tokens") or 0
            inputs = r.get("input_tokens") or 1
            cost   = r.get("cost") or 0.0
            # Custo médio por token de input do provedor neste período
            avg_cost_per_token = cost / max(inputs, 1)
            # Sem cache, esses cached_tokens custariam o normal
            # Com cache, custaram ~10% (Anthropic) ou ~50% (OpenAI)
            saving_pct = 0.90 if r["provider"] == "anthropic" else 0.50
            total_saved += cached * avg_cost_per_token * saving_pct
        return total_saved


# Instância global
metrics = Observability()
