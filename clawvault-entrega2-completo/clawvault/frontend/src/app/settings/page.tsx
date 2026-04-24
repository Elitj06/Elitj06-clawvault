"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Copy } from "lucide-react";
import { api, SystemStatus, ModelInfo } from "@/lib/api";

const PROVIDER_INFO: Record<string, { url: string; free: boolean; note: string }> = {
  openrouter: {
    url: "https://openrouter.ai/settings/keys",
    free: true,
    note: "300+ modelos numa só chave. Inclui grátis.",
  },
  anthropic: {
    url: "https://console.anthropic.com/settings/keys",
    free: false,
    note: "Claude (Opus, Sonnet, Haiku)",
  },
  openai: {
    url: "https://platform.openai.com/api-keys",
    free: false,
    note: "GPT-5, GPT-4o",
  },
  google: {
    url: "https://aistudio.google.com/app/apikey",
    free: true,
    note: "Gemini — 1500 req/dia grátis",
  },
  deepseek: {
    url: "https://platform.deepseek.com/api_keys",
    free: false,
    note: "Muito barato, ótimo em código",
  },
  zai: {
    url: "https://z.ai/model-api",
    free: true,
    note: "GLM — tem modelos 100% grátis",
  },
  groq: {
    url: "https://console.groq.com/keys",
    free: true,
    note: "Ultra rápido — free tier 30 req/min",
  },
  moonshot: {
    url: "https://platform.moonshot.ai/console/api-keys",
    free: false,
    note: "Kimi — 262k contexto",
  },
  minimax: {
    url: "https://www.minimax.io/platform",
    free: false,
    note: "M2.5: 80% SWE-bench",
  },
  alibaba: {
    url: "https://dashscope.console.aliyun.com/apiKey",
    free: false,
    note: "Qwen — modelos variados",
  },
};

export default function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);

  useEffect(() => {
    api.getStatus().then(setStatus);
    api.getModels().then((d) => setModels(d.models));
  }, []);

  function copyEnvVar(name: string) {
    navigator.clipboard.writeText(name);
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-8">
        <div className="font-mono text-xs text-ink-500 uppercase tracking-wider mb-1">
          Configurações
        </div>
        <h1 className="font-display text-4xl font-bold tracking-tight text-ink-900">
          Providers e sistema
        </h1>
      </div>

      <div className="card p-6 mb-6">
        <h2 className="font-display text-lg font-semibold mb-4">
          Providers de LLM
        </h2>
        <div className="space-y-3">
          {status &&
            Object.entries(status.providers).map(([name, active]) => {
              const info = PROVIDER_INFO[name];
              const envVar =
                name === "alibaba"
                  ? "DASHSCOPE_API_KEY"
                  : `${name.toUpperCase()}_API_KEY`;

              return (
                <div
                  key={name}
                  className="flex items-center gap-4 p-3 rounded-md border border-ink-100"
                >
                  {active ? (
                    <CheckCircle2 className="text-signal-success" size={20} />
                  ) : (
                    <Circle className="text-ink-300" size={20} />
                  )}
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-ink-900 capitalize">
                        {name}
                      </span>
                      {info?.free && <span className="badge-accent">grátis</span>}
                    </div>
                    {info && (
                      <div className="text-xs text-ink-500 mt-0.5">
                        {info.note}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => copyEnvVar(envVar)}
                    className="text-[10px] font-mono text-ink-500 hover:text-ink-900 flex items-center gap-1"
                    title="Copiar nome da variável"
                  >
                    <Copy size={10} /> {envVar}
                  </button>
                  {!active && info && (
                    <a
                      href={info.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-secondary text-xs"
                    >
                      Obter chave
                    </a>
                  )}
                </div>
              );
            })}
        </div>
        <p className="text-xs text-ink-500 mt-4">
          Chaves de API são configuradas no arquivo{" "}
          <code className="font-mono bg-ink-50 px-1.5 py-0.5 rounded">
            .env
          </code>{" "}
          na raiz do projeto. Reinicie o servidor após mudar.
        </p>
      </div>

      <div className="card p-6 mb-6">
        <h2 className="font-display text-lg font-semibold mb-4">
          Modelos disponíveis
        </h2>
        <div className="text-sm text-ink-600 mb-4">
          Total: <strong>{models.length}</strong> modelos catalogados ·{" "}
          <strong>{models.filter((m) => m.available).length}</strong>{" "}
          disponíveis com suas chaves atuais
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {models.map((m) => (
            <div
              key={m.id}
              className={`p-3 border rounded text-sm ${
                m.available
                  ? "border-ink-200 bg-white"
                  : "border-ink-100 bg-ink-50/50 opacity-60"
              }`}
            >
              <div className="font-mono text-xs font-medium text-ink-900">
                {m.id}
              </div>
              <div className="text-[11px] text-ink-500 mt-0.5 flex items-center gap-2">
                <span>{m.provider}</span>
                <span>·</span>
                <span>
                  {m.cost_input === 0 ? "🆓" : `$${m.cost_input}/$${m.cost_output}`}
                </span>
                <span>·</span>
                <span>{(m.context_window / 1000).toFixed(0)}k ctx</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card p-6">
        <h2 className="font-display text-lg font-semibold mb-4">Sistema</h2>
        <dl className="grid grid-cols-2 gap-y-3 text-sm">
          <dt className="text-ink-500">Versão</dt>
          <dd className="font-mono">{status?.version}</dd>
          <dt className="text-ink-500">Conversas totais</dt>
          <dd className="font-mono">{status?.stats.conversations}</dd>
          <dt className="text-ink-500">Mensagens totais</dt>
          <dd className="font-mono">{status?.stats.messages}</dd>
          <dt className="text-ink-500">Agentes registrados</dt>
          <dd className="font-mono">{status?.stats.agents}</dd>
        </dl>
      </div>
    </div>
  );
}
