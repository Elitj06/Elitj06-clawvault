"use client";

/**
 * Página /usage — Observability completa
 * =======================================
 * Consome os endpoints /api/observability/* (P3) para mostrar:
 *   - Cards com métricas-chave (custo, cache hit rate, calls, taxa erro)
 *   - Gráfico de timeline (custo por dia)
 *   - Tabela de modelos (custo, calls, taxa de sucesso)
 *   - Tabela de agentes
 *   - Top conversas
 */

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

type Overview = {
  period_days: number;
  calls: number;
  success: number;
  errors: number;
  success_rate: number;
  tokens: { input: number; output: number; cached: number; total: number };
  cache_hit_rate: number;
  cost_usd: number;
  cost_saved_usd: number;
  cost_per_day_usd: number;
};

type ModelRow = {
  model_id: string;
  provider: string;
  calls: number;
  success: number;
  success_rate: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  cost_usd: number;
};

type AgentRow = {
  agent_name: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  cost_usd: number;
};

type TimelineRow = {
  bucket: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  cost_usd: number;
};

type ConversationRow = {
  id: number;
  title: string;
  agent_name: string;
  total_tokens: number;
  total_cost_usd: number;
  created_at: string;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtUsd(v: number): string {
  if (v < 0.01) return `$${v.toFixed(6)}`;
  if (v < 1)    return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

function fmtNum(v: number): string {
  return v.toLocaleString("pt-BR");
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function UsagePage() {
  const [period, setPeriod] = useState<number>(7);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [models, setModels] = useState<ModelRow[]>([]);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [timeline, setTimeline] = useState<TimelineRow[]>([]);
  const [conversations, setConversations] = useState<ConversationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const [ov, md, ag, tl, tc] = await Promise.all([
          fetch(`${API_URL}/api/observability/overview?days=${period}`).then((r) => r.json()),
          fetch(`${API_URL}/api/observability/by-model?days=${period}`).then((r) => r.json()),
          fetch(`${API_URL}/api/observability/by-agent?days=${period}`).then((r) => r.json()),
          fetch(`${API_URL}/api/observability/timeline?days=${period}`).then((r) => r.json()),
          fetch(`${API_URL}/api/observability/top-conversations?limit=10`).then((r) => r.json()),
        ]);
        if (cancelled) return;
        setOverview(ov);
        setModels(md.models || []);
        setAgents(ag.agents || []);
        setTimeline(tl.timeline || []);
        setConversations(tc.conversations || []);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        if (!cancelled) setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [period]);

  // -------------------------------------------------------------------------
  // Cálculos derivados pra timeline (gráfico)
  // -------------------------------------------------------------------------

  const maxCost = Math.max(0.0001, ...timeline.map((t) => t.cost_usd));

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div>
      {/* HEADER */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-ink-400 mb-1 font-mono">
            uso e custos
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-ink-900">
            Observability
          </h1>
        </div>

        {/* Seletor de período */}
        <div className="flex gap-1 bg-ink-100 rounded-lg p-1">
          {[1, 7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setPeriod(d)}
              className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                period === d
                  ? "bg-white shadow-sm text-ink-900 font-semibold"
                  : "text-ink-500 hover:text-ink-700"
              }`}
            >
              {d === 1 ? "1 dia" : `${d} dias`}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="bg-white rounded-xl border border-ink-100 p-8 text-center text-ink-500">
          carregando métricas…
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
          Erro ao carregar: {error}
        </div>
      )}

      {!loading && !error && overview && (
        <>
          {/* CARDS DE MÉTRICAS-CHAVE */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <MetricCard
              label="custo total"
              value={fmtUsd(overview.cost_usd)}
              hint={`${fmtUsd(overview.cost_per_day_usd)}/dia`}
              color="violet"
            />
            <MetricCard
              label="cache hit rate"
              value={fmtPct(overview.cache_hit_rate)}
              hint={`${fmtNum(overview.tokens.cached)} tokens cacheados`}
              color="cyan"
            />
            <MetricCard
              label="economizado pelo cache"
              value={fmtUsd(overview.cost_saved_usd)}
              hint="estimativa via prompt caching"
              color="green"
            />
            <MetricCard
              label="chamadas"
              value={fmtNum(overview.calls)}
              hint={`${fmtPct(overview.success_rate)} sucesso · ${overview.errors} erros`}
              color={overview.errors > 0 ? "amber" : "ink"}
            />
          </div>

          {/* TIMELINE */}
          <div className="bg-white rounded-xl border border-ink-100 p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-ink-900">
                Evolução diária — custo
              </h2>
              <span className="text-[10px] font-mono text-ink-400">
                últimos {period} dias
              </span>
            </div>
            {timeline.length === 0 ? (
              <div className="text-center text-ink-400 text-sm py-8">
                Sem dados no período
              </div>
            ) : (
              <div className="flex items-end gap-1 h-40">
                {timeline.map((t) => {
                  const h = (t.cost_usd / maxCost) * 100;
                  return (
                    <div
                      key={t.bucket}
                      className="flex-1 flex flex-col items-center gap-1 group relative"
                    >
                      <div
                        className="w-full bg-violet-400 hover:bg-violet-500 transition-colors rounded-t"
                        style={{ height: `${Math.max(h, 2)}%` }}
                        title={`${t.bucket}: ${fmtUsd(t.cost_usd)} · ${t.calls} calls`}
                      />
                      <div className="text-[8px] font-mono text-ink-400 truncate w-full text-center">
                        {t.bucket.slice(5)}
                      </div>
                      {/* Tooltip */}
                      <div className="absolute bottom-full mb-2 hidden group-hover:block bg-ink-900 text-white text-[10px] font-mono rounded px-2 py-1 whitespace-nowrap z-10">
                        {fmtUsd(t.cost_usd)} · {t.calls} calls
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* GRID 2 COLUNAS: Modelos + Agentes */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* MODELOS */}
            <div className="bg-white rounded-xl border border-ink-100 overflow-hidden">
              <div className="px-6 py-4 border-b border-ink-100">
                <h2 className="text-sm font-semibold text-ink-900">
                  Modelos por custo
                </h2>
              </div>
              {models.length === 0 ? (
                <div className="p-6 text-center text-ink-400 text-sm">sem dados</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-ink-50 text-[10px] uppercase tracking-wider text-ink-500 font-mono">
                    <tr>
                      <th className="text-left px-4 py-2">modelo</th>
                      <th className="text-right px-4 py-2">calls</th>
                      <th className="text-right px-4 py-2">sucesso</th>
                      <th className="text-right px-4 py-2">custo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {models.slice(0, 10).map((m) => (
                      <tr key={`${m.provider}/${m.model_id}`} className="border-t border-ink-100 hover:bg-ink-50/50">
                        <td className="px-4 py-2">
                          <div className="font-medium text-ink-800 truncate max-w-[200px]">
                            {m.model_id}
                          </div>
                          <div className="text-[10px] font-mono text-ink-400">{m.provider}</div>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">{m.calls}</td>
                        <td className="px-4 py-2 text-right tabular-nums">
                          <span className={m.success_rate < 0.9 ? "text-amber-600" : "text-ink-700"}>
                            {fmtPct(m.success_rate)}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums font-medium">
                          {fmtUsd(m.cost_usd)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* AGENTES */}
            <div className="bg-white rounded-xl border border-ink-100 overflow-hidden">
              <div className="px-6 py-4 border-b border-ink-100">
                <h2 className="text-sm font-semibold text-ink-900">
                  Agentes por uso
                </h2>
              </div>
              {agents.length === 0 ? (
                <div className="p-6 text-center text-ink-400 text-sm">sem dados</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-ink-50 text-[10px] uppercase tracking-wider text-ink-500 font-mono">
                    <tr>
                      <th className="text-left px-4 py-2">agente</th>
                      <th className="text-right px-4 py-2">calls</th>
                      <th className="text-right px-4 py-2">tokens</th>
                      <th className="text-right px-4 py-2">custo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agents.slice(0, 10).map((a) => (
                      <tr key={a.agent_name} className="border-t border-ink-100 hover:bg-ink-50/50">
                        <td className="px-4 py-2 font-medium text-ink-800">{a.agent_name}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{a.calls}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-ink-500">
                          {fmtNum(a.input_tokens + a.output_tokens)}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums font-medium">
                          {fmtUsd(a.cost_usd)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* TOP CONVERSAS */}
          <div className="bg-white rounded-xl border border-ink-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-ink-100">
              <h2 className="text-sm font-semibold text-ink-900">
                Conversas mais caras (último mês)
              </h2>
            </div>
            {conversations.length === 0 ? (
              <div className="p-6 text-center text-ink-400 text-sm">sem dados</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-ink-50 text-[10px] uppercase tracking-wider text-ink-500 font-mono">
                  <tr>
                    <th className="text-left px-4 py-2">título</th>
                    <th className="text-left px-4 py-2">agente</th>
                    <th className="text-right px-4 py-2">tokens</th>
                    <th className="text-right px-4 py-2">custo</th>
                    <th className="text-right px-4 py-2">data</th>
                  </tr>
                </thead>
                <tbody>
                  {conversations.map((c) => (
                    <tr key={c.id} className="border-t border-ink-100 hover:bg-ink-50/50">
                      <td className="px-4 py-2 truncate max-w-[300px] text-ink-800">
                        {c.title || `(sem título) #${c.id}`}
                      </td>
                      <td className="px-4 py-2 text-ink-600">{c.agent_name}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{fmtNum(c.total_tokens)}</td>
                      <td className="px-4 py-2 text-right tabular-nums font-medium">
                        {fmtUsd(c.total_cost_usd)}
                      </td>
                      <td className="px-4 py-2 text-right text-[10px] font-mono text-ink-400">
                        {c.created_at?.slice(0, 10)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponentes
// ---------------------------------------------------------------------------

function MetricCard({
  label,
  value,
  hint,
  color,
}: {
  label: string;
  value: string;
  hint: string;
  color: "violet" | "cyan" | "green" | "amber" | "ink";
}) {
  const colors = {
    violet: "text-violet-600 bg-violet-50",
    cyan:   "text-cyan-600 bg-cyan-50",
    green:  "text-green-600 bg-green-50",
    amber:  "text-amber-600 bg-amber-50",
    ink:    "text-ink-700 bg-ink-50",
  };
  return (
    <div className="bg-white rounded-xl border border-ink-100 p-5">
      <div className={`inline-block px-2 py-0.5 rounded text-[9px] uppercase tracking-wider font-mono mb-3 ${colors[color]}`}>
        {label}
      </div>
      <div className="text-2xl font-bold tabular-nums text-ink-900 mb-1">
        {value}
      </div>
      <div className="text-[10px] font-mono text-ink-400">{hint}</div>
    </div>
  );
}
