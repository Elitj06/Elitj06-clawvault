"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { api, UsageByModel, UsageDaily } from "@/lib/api";

export default function UsagePage() {
  const [byModel, setByModel] = useState<UsageByModel[]>([]);
  const [daily, setDaily] = useState<UsageDaily[]>([]);
  const [days, setDays] = useState(30);

  useEffect(() => {
    api.usageByModel(days).then((d) => setByModel(d.usage));
    api.usageDaily(days).then((d) => setDaily(d.daily));
  }, [days]);

  const totalCost = byModel.reduce((s, m) => s + (m.total_cost || 0), 0);
  const totalTokens = byModel.reduce(
    (s, m) => s + (m.input_tokens || 0) + (m.output_tokens || 0),
    0
  );
  const totalCalls = byModel.reduce((s, m) => s + (m.calls || 0), 0);

  const pieColors = ["#d4a574", "#a67238", "#865a2c", "#c28e50", "#c99e45"];

  return (
    <div className="animate-fade-in">
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="font-mono text-xs text-ink-500 uppercase tracking-wider mb-1">
            Uso e custos
          </div>
          <h1 className="font-display text-4xl font-bold tracking-tight text-ink-900">
            Análise detalhada
          </h1>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="text-sm px-3 py-2 border border-ink-200 rounded bg-white"
        >
          <option value={7}>Últimos 7 dias</option>
          <option value={30}>Últimos 30 dias</option>
          <option value={90}>Últimos 90 dias</option>
        </select>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="card p-5">
          <div className="font-mono text-xs text-ink-500 uppercase tracking-wider mb-2">
            Custo total
          </div>
          <div className="font-display text-3xl font-bold text-ink-900">
            ${totalCost.toFixed(4)}
          </div>
        </div>
        <div className="card p-5">
          <div className="font-mono text-xs text-ink-500 uppercase tracking-wider mb-2">
            Chamadas
          </div>
          <div className="font-display text-3xl font-bold text-ink-900">
            {totalCalls.toLocaleString("pt-BR")}
          </div>
        </div>
        <div className="card p-5">
          <div className="font-mono text-xs text-ink-500 uppercase tracking-wider mb-2">
            Tokens processados
          </div>
          <div className="font-display text-3xl font-bold text-ink-900">
            {totalTokens.toLocaleString("pt-BR")}
          </div>
        </div>
      </div>

      {daily.length > 0 && (
        <div className="card p-6 mb-6">
          <h2 className="font-display text-lg font-semibold mb-4">
            Custo diário
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={daily}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e4e3e0" />
              <XAxis dataKey="day" fontSize={11} stroke="#82807a" />
              <YAxis
                fontSize={11}
                stroke="#82807a"
                tickFormatter={(v) => `$${v.toFixed(2)}`}
              />
              <Tooltip
                contentStyle={{
                  background: "#fff",
                  border: "1px solid #e4e3e0",
                  borderRadius: "6px",
                  fontSize: "12px",
                }}
              />
              <Line
                type="monotone"
                dataKey="cost"
                stroke="#c28e50"
                strokeWidth={2}
                dot={{ fill: "#c28e50", r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {byModel.length > 0 && (
          <>
            <div className="card p-6">
              <h2 className="font-display text-lg font-semibold mb-4">
                Custo por modelo
              </h2>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={byModel.slice(0, 5).map((m) => ({
                      name: m.model_id,
                      value: m.total_cost,
                    }))}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={50}
                    outerRadius={90}
                  >
                    {byModel.slice(0, 5).map((_, i) => (
                      <Cell key={i} fill={pieColors[i % pieColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: number) => `$${v.toFixed(4)}`}
                    contentStyle={{
                      background: "#fff",
                      border: "1px solid #e4e3e0",
                      borderRadius: "6px",
                      fontSize: "12px",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="card p-6">
              <h2 className="font-display text-lg font-semibold mb-4">
                Chamadas por modelo
              </h2>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={byModel.slice(0, 8)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e4e3e0" />
                  <XAxis type="number" fontSize={11} stroke="#82807a" />
                  <YAxis
                    type="category"
                    dataKey="model_id"
                    fontSize={10}
                    stroke="#82807a"
                    width={100}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#fff",
                      border: "1px solid #e4e3e0",
                      borderRadius: "6px",
                      fontSize: "12px",
                    }}
                  />
                  <Bar dataKey="calls" fill="#d4a574" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>

      {/* Tabela detalhada */}
      {byModel.length > 0 && (
        <div className="card overflow-hidden mt-6">
          <table className="w-full text-sm">
            <thead className="bg-ink-50 border-b border-ink-100">
              <tr>
                <th className="text-left px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
                  Modelo
                </th>
                <th className="text-left px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
                  Provider
                </th>
                <th className="text-right px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
                  Calls
                </th>
                <th className="text-right px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
                  In
                </th>
                <th className="text-right px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
                  Out
                </th>
                <th className="text-right px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
                  Custo
                </th>
              </tr>
            </thead>
            <tbody>
              {byModel.map((m) => (
                <tr
                  key={m.model_id}
                  className="border-b border-ink-100 last:border-0"
                >
                  <td className="px-4 py-2.5 font-mono text-xs">{m.model_id}</td>
                  <td className="px-4 py-2.5">
                    <span className="badge-muted">{m.provider}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono">
                    {m.calls}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs">
                    {(m.input_tokens || 0).toLocaleString("pt-BR")}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs">
                    {(m.output_tokens || 0).toLocaleString("pt-BR")}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono">
                    ${(m.total_cost || 0).toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
