"use client";

import { useEffect, useState } from "react";
import { Plus, Star, Users, ChevronRight, Bot, Brain } from "lucide-react";
import { api, Agent, AgentMemoryStats } from "@/lib/api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<{
    agent: Agent;
    memory_stats: AgentMemoryStats;
    subagents: Agent[];
  } | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const d = await api.listAgents();
      setAgents(d.agents || []);
      if (d.agents && d.agents.length > 0 && !selected) {
        setSelected(d.agents[0].name);
      }
    } catch (e: any) {
      setError(e.message || "Erro ao carregar agentes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (selected) {
      api.getAgent(selected).then(setDetail).catch(() => setDetail(null));
    }
  }, [selected]);

  return (
    <div className="animate-fade-in px-2 sm:px-0">
      <div className="mb-4 sm:mb-6 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <div className="font-mono text-xs text-ink-500 dark:text-ink-400 uppercase tracking-wider mb-1">
            Agentes
          </div>
          <h1 className="font-display text-xl sm:text-2xl font-bold tracking-tight text-ink-900 dark:text-ink-50">
            Agentes e sub-agentes
          </h1>
          <p className="text-ink-500 dark:text-ink-400 mt-1 text-xs sm:text-sm">
            Gerencie seu agente principal e sub-agentes especializados
          </p>
        </div>
        <button className="btn-primary whitespace-nowrap text-xs" onClick={() => setShowCreate(true)}>
          <Plus size={14} /> Criar sub-agente
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800/30 text-red-600 dark:text-red-400 text-xs">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-5 h-5 border-2 border-ink-200 border-t-accent-400 rounded-full animate-spin" />
        </div>
      ) : agents.length === 0 ? (
        <div className="card p-8 text-center">
          <Bot size={32} className="mx-auto text-ink-300 dark:text-ink-600 mb-3" />
          <p className="text-ink-400 text-sm">Nenhum agente encontrado.</p>
          <button className="btn-primary mt-3 text-xs" onClick={load}>Recarregar</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 sm:gap-4">
          {/* Lista */}
          <div className="lg:col-span-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-2">
            {agents.map((agent) => (
              <button
                key={agent.name}
                onClick={() => setSelected(agent.name)}
                className={`w-full text-left card p-3 sm:p-4 card-hover transition-all ${
                  selected === agent.name ? "border-accent-300 bg-accent-50/30 dark:bg-accent-900/20 ring-1 ring-accent-300/30" : ""
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  {agent.is_main ? (
                    <Star size={14} className="text-accent-500 fill-accent-400 shrink-0" />
                  ) : (
                    <Users size={14} className="text-ink-400 dark:text-ink-500 shrink-0" />
                  )}
                  <span className="font-medium text-sm text-ink-900 dark:text-ink-50 truncate">{agent.name}</span>
                  {agent.parent_agent && (
                    <span className="font-mono text-[10px] text-ink-400 dark:text-ink-500 shrink-0">
                      ← {agent.parent_agent}
                    </span>
                  )}
                </div>
                <div className="text-xs text-ink-500 dark:text-ink-400 line-clamp-2 pl-6">
                  {agent.role}
                </div>
              </button>
            ))}
          </div>

          {/* Detalhes */}
          <div className="lg:col-span-8">
            {detail ? (
              <AgentDetail detail={detail} />
            ) : selected ? (
              <div className="card p-8 text-center text-ink-400 dark:text-ink-500">
                <div className="w-4 h-4 border-2 border-ink-200 border-t-accent-400 rounded-full animate-spin mx-auto mb-3" />
                Carregando detalhes...
              </div>
            ) : (
              <div className="card p-8 text-center text-ink-400 dark:text-ink-500">
                Selecione um agente para ver detalhes
              </div>
            )}
          </div>
        </div>
      )}

      {showCreate && (
        <CreateAgentModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function AgentDetail({
  detail,
}: {
  detail: { agent: Agent; memory_stats: AgentMemoryStats; subagents: Agent[] };
}) {
  const { agent, memory_stats, subagents } = detail;

  return (
    <div className="space-y-3 sm:space-y-4">
      <div className="card p-4 sm:p-6">
        <div className="flex items-center gap-3 mb-1">
          {agent.is_main ? (
            <Star className="text-accent-500 fill-accent-400 shrink-0" size={20} />
          ) : (
            <Users className="text-ink-400 dark:text-ink-500 shrink-0" size={20} />
          )}
          <h2 className="font-display text-lg sm:text-xl font-semibold text-ink-900 dark:text-ink-50 truncate">
            {agent.name}
          </h2>
        </div>
        <p className="text-ink-600 dark:text-ink-300 mt-2 text-sm">{agent.role}</p>

        <div className="grid grid-cols-3 gap-2 sm:gap-4 mt-4 sm:mt-6 pt-4 sm:pt-6 border-t border-ink-100 dark:border-ink-700">
          <Field label="Pai" value={agent.parent_agent || "—"} />
          <Field label="Modelo" value={agent.preferred_model || "auto"} />
          <Field label="Chamadas" value={String(agent.total_calls || 0)} />
        </div>
      </div>

      <div className="card p-4 sm:p-6">
        <h3 className="font-display text-sm sm:text-base font-semibold text-ink-900 dark:text-ink-50 mb-3 flex items-center gap-2">
          <Brain size={16} className="text-ink-400" />
          Memória progressiva
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-3">
          <MemoryLevelCard
            level="core"
            label="CORE"
            hint="Fatos fundamentais (sempre no contexto)"
            stats={memory_stats.core}
            color="accent"
          />
          <MemoryLevelCard
            level="learned"
            label="LEARNED"
            hint="Padrões aprendidos (por relevância)"
            stats={memory_stats.learned}
            color="ink"
          />
          <MemoryLevelCard
            level="episodic"
            label="EPISODIC"
            hint="Últimas experiências (consolida em 10)"
            stats={memory_stats.episodic}
            color="signal"
          />
        </div>
      </div>

      {subagents.length > 0 && (
        <div className="card p-4 sm:p-6">
          <h3 className="font-display text-sm sm:text-base font-semibold text-ink-900 dark:text-ink-50 mb-3">
            Sub-agentes ({subagents.length})
          </h3>
          <div className="space-y-2">
            {subagents.map((sa) => (
              <div
                key={sa.name}
                className="flex items-center justify-between px-3 py-2 rounded-md bg-ink-50 dark:bg-ink-800 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <span className="font-medium text-ink-900 dark:text-ink-50">{sa.name}</span>
                  <span className="text-ink-500 dark:text-ink-400 ml-2 text-xs">{sa.role}</span>
                </div>
                <ChevronRight size={14} className="text-ink-400 dark:text-ink-500 shrink-0" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-wider text-ink-500 dark:text-ink-400">
        {label}
      </div>
      <div className="text-xs sm:text-sm text-ink-800 dark:text-ink-200 mt-1 truncate">{value}</div>
    </div>
  );
}

function MemoryLevelCard({
  label,
  hint,
  stats,
}: {
  level: string;
  label: string;
  hint: string;
  stats: { entries: number; tokens: number };
  color: string;
}) {
  return (
    <div className="border border-ink-100 dark:border-ink-700 rounded-md p-3 sm:p-4">
      <div className="font-mono text-xs font-semibold text-ink-700 dark:text-ink-300 mb-1">
        {label}
      </div>
      <div className="font-display text-xl sm:text-2xl font-bold text-ink-900 dark:text-ink-50 mb-1">
        {stats.entries}
      </div>
      <div className="text-xs text-ink-500 dark:text-ink-400 mb-2">~{stats.tokens} tokens</div>
      <div className="text-[10px] text-ink-400 dark:text-ink-500">{hint}</div>
    </div>
  );
}

function CreateAgentModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [model, setModel] = useState("");
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!name || !role) return;
    setSaving(true);
    try {
      await api.createAgent({
        name,
        role,
        parent_agent: "main",
        preferred_model: model || undefined,
      });
      onCreated();
    } catch (e: any) {
      alert(`Erro: ${e.message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-ink-900/40 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in p-4">
      <div className="bg-white dark:bg-ink-800 rounded-lg p-5 sm:p-6 w-full max-w-md animate-slide-up">
        <h2 className="font-display text-lg font-semibold mb-4 dark:text-ink-50">
          Criar sub-agente
        </h2>
        <div className="space-y-3">
          <div>
            <label className="label">Nome (sem espaços)</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value.replace(/\s+/g, "-"))}
              placeholder="code-reviewer"
            />
          </div>
          <div>
            <label className="label">Função</label>
            <input
              className="input"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="Revisor de código Python/TS"
            />
          </div>
          <div>
            <label className="label">Modelo preferido (opcional)</label>
            <input
              className="input"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="ex: claude-sonnet-4-6 ou glm-4.7"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <button className="btn-ghost" onClick={onClose}>
            Cancelar
          </button>
          <button
            className="btn-primary"
            onClick={save}
            disabled={!name || !role || saving}
          >
            Criar
          </button>
        </div>
      </div>
    </div>
  );
}
