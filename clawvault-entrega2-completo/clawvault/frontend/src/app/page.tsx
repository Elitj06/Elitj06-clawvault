"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  DollarSign,
  MessageSquare,
  Users,
  Zap,
  TrendingDown,
  Layers,
} from "lucide-react";
import { api, SystemStatus, UsageDaily } from "@/lib/api";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function HomePage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [daily, setDaily] = useState<UsageDaily[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getStatus(), api.usageDaily(30)])
      .then(([s, d]) => {
        setStatus(s);
        setDaily(d.daily);
      })
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <LoadingState />;
  }

  if (!status) {
    return <ErrorState />;
  }

  const providersOnline = Object.values(status.providers).filter(Boolean).length;
  const providersTotal = Object.keys(status.providers).length;

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <div className="font-mono text-xs text-ink-500 dark:text-ink-400 uppercase tracking-wider mb-1">
          Dashboard
        </div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-ink-900 dark:text-ink-50">
          Visão geral
        </h1>
        <p className="text-ink-500 dark:text-ink-400 mt-1 text-sm sm:text-base">
          Status do seu sistema de agentes multi-LLM
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
        <StatCard
          icon={<DollarSign size={18} />}
          label="Gasto do mês"
          value={`$${status.budget.spent_usd.toFixed(2)}`}
          hint={`de $${status.budget.limit_usd.toFixed(0)} (${status.budget.percent_used.toFixed(0)}%)`}
          progress={status.budget.percent_used}
        />
        <StatCard
          icon={<Zap size={18} />}
          label="Providers ativos"
          value={`${providersOnline}/${providersTotal}`}
          hint="com chave configurada"
        />
        <StatCard
          icon={<MessageSquare size={18} />}
          label="Conversas"
          value={status.stats.conversations.toString()}
          hint="no total"
        />
        <StatCard
          icon={<Users size={18} />}
          label="Agentes"
          value={status.stats.agents.toString()}
          hint="registrados"
        />
      </div>

      {/* Grid: gráfico + quick actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="font-mono text-xs text-ink-500 dark:text-ink-400 uppercase tracking-wider mb-1">
                Últimos 30 dias
              </div>
              <h2 className="font-display text-xl font-semibold text-ink-900 dark:text-ink-50">
                Custo diário
              </h2>
            </div>
            <Link
              href="/usage"
              className="text-sm text-ink-500 dark:text-ink-400 hover:text-ink-900 dark:hover:text-ink-50 flex items-center gap-1"
            >
              Ver detalhes <ArrowRight size={14} />
            </Link>
          </div>

          {daily.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={daily}>
                <defs>
                  <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#d4a574" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#d4a574" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e3e0" />
                <XAxis
                  dataKey="day"
                  fontSize={11}
                  stroke="#82807a"
                  tickFormatter={(d) => d.slice(5)}
                />
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
                  formatter={(v: number) => [`$${v.toFixed(4)}`, "Custo"]}
                />
                <Area
                  type="monotone"
                  dataKey="cost"
                  stroke="#c28e50"
                  strokeWidth={2}
                  fill="url(#costGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="Nenhum uso registrado ainda" />
          )}
        </div>

        {/* Quick actions */}
        <div className="space-y-4">
          <div className="card p-6">
            <h3 className="font-display font-semibold text-ink-900 dark:text-ink-50 mb-3">
              Início rápido
            </h3>
            <div className="space-y-2">
              <QuickLink
                href="/chat"
                icon={<MessageSquare size={14} />}
                label="Iniciar conversa"
              />
              <QuickLink
                href="/agents"
                icon={<Users size={14} />}
                label="Criar sub-agente"
              />
              <QuickLink
                href="/whatsapp"
                icon={<Layers size={14} />}
                label="Conectar WhatsApp"
              />
            </div>
          </div>

          <div className="card p-6 bg-accent-50 dark:bg-accent-900/30 border-accent-200 dark:border-accent-700">
            <div className="flex items-start gap-3">
              <TrendingDown size={16} className="text-accent-700 dark:text-accent-400 mt-0.5" />
              <div>
                <h3 className="font-display font-semibold text-accent-900 dark:text-accent-200 text-sm">
                  Economia ativa
                </h3>
                <p className="text-xs text-accent-700 dark:text-accent-400 mt-1">
                  Compressão automática + roteamento inteligente reduzem seu gasto
                  em até 70%.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Providers overview */}
      <div className="mt-6 card p-6">
        <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-ink-50 mb-4">
          Providers configurados
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
          {Object.entries(status.providers).map(([name, active]) => (
            <div
              key={name}
              className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm ${
                active
                  ? "border-ink-200 dark:border-ink-700 bg-ink-50 dark:bg-ink-900"
                  : "border-ink-100 dark:border-ink-700 bg-ink-50/50 dark:bg-ink-900/50 opacity-50"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  active ? "bg-signal-success" : "bg-ink-300 dark:bg-ink-600"
                }`}
              />
              <span className="font-mono text-xs capitalize dark:text-ink-300">{name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  hint,
  progress,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint: string;
  progress?: number;
}) {
  return (
    <div className="card p-4 sm:p-5 card-hover">
      <div className="flex items-center justify-between mb-3 sm:mb-4">
        <div className="font-mono text-[10px] sm:text-xs text-ink-500 dark:text-ink-400 uppercase tracking-wider">
          {label}
        </div>
        <div className="text-ink-400 dark:text-ink-500">{icon}</div>
      </div>
      <div className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink-900 dark:text-ink-50">
        {value}
      </div>
      <div className="text-[10px] sm:text-xs text-ink-500 dark:text-ink-400 mt-1">{hint}</div>
      {typeof progress === "number" && (
        <div className="mt-3 h-1 bg-ink-100 dark:bg-ink-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              progress > 80
                ? "bg-signal-danger"
                : progress > 60
                  ? "bg-signal-warning"
                  : "bg-accent-400"
            }`}
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}

function QuickLink({
  href,
  icon,
  label,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between px-3 py-2 rounded-md text-sm hover:bg-ink-50 dark:hover:bg-ink-800 transition-colors group"
    >
      <div className="flex items-center gap-2 text-ink-700 dark:text-ink-300">
        {icon}
        <span>{label}</span>
      </div>
      <ArrowRight
        size={14}
        className="text-ink-300 dark:text-ink-600 group-hover:text-ink-700 dark:group-hover:text-ink-300 transition-colors"
      />
    </Link>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="h-[220px] flex items-center justify-center text-ink-400 dark:text-ink-500 text-sm">
      {message}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-10 bg-ink-100 dark:bg-ink-800 rounded w-48 sm:w-64" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 sm:h-32 bg-ink-100 dark:bg-ink-800 rounded" />
        ))}
      </div>
      <div className="h-64 bg-ink-100 dark:bg-ink-800 rounded" />
    </div>
  );
}

function ErrorState() {
  return (
    <div className="card p-8 text-center">
      <p className="text-ink-500 dark:text-ink-400">
        Erro ao carregar dados. Verifique se o backend está rodando em{" "}
        <code className="font-mono text-xs bg-ink-100 dark:bg-ink-700 px-1.5 py-0.5 rounded">
          localhost:8000
        </code>
      </p>
    </div>
  );
}
