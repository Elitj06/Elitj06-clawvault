"use client";

import { useEffect, useState } from "react";
import {
  QrCode,
  MessageCircle,
  CheckCircle2,
  XCircle,
  Send,
  Settings,
  Ban,
  RefreshCw,
} from "lucide-react";
import { api, WhatsAppContact } from "@/lib/api";

export default function WhatsAppPage() {
  const [status, setStatus] = useState<any>(null);
  const [config, setConfig] = useState<Record<string, any>>({});
  const [contacts, setContacts] = useState<WhatsAppContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"status" | "contacts" | "config">(
    "status"
  );
  const [sendForm, setSendForm] = useState({ phone: "", message: "" });

  async function loadAll() {
    try {
      const [s, c, ct] = await Promise.all([
        api.whatsappStatus(),
        api.whatsappConfig(),
        api.listContacts().catch(() => ({ contacts: [] })),
      ]);
      setStatus(s);
      setConfig(c);
      setContacts(ct.contacts || []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 10000); // refresh a cada 10s
    return () => clearInterval(interval);
  }, []);

  async function fetchQr() {
    try {
      const r = await api.getQrcode();
      // Evolution retorna { base64: 'data:image/png;base64,...' } ou { code: '...' }
      setQrCode(r.base64 || r.code || null);
    } catch (e: any) {
      alert("Erro ao buscar QR Code: " + e.message);
    }
  }

  async function createInstance() {
    try {
      await api.createWhatsappInstance();
      alert("Instância criada! Agora busque o QR Code para escanear.");
      loadAll();
    } catch (e: any) {
      alert("Erro: " + e.message);
    }
  }

  async function sendMessage() {
    if (!sendForm.phone || !sendForm.message) return;
    try {
      await api.sendWhatsappMessage(sendForm.phone, sendForm.message);
      setSendForm({ phone: "", message: "" });
      alert("Mensagem enviada!");
    } catch (e: any) {
      alert("Erro: " + e.message);
    }
  }

  async function updateConfig(key: string, value: any) {
    await api.updateWhatsappConfig(key, value);
    setConfig({ ...config, [key]: value });
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-8 flex items-start justify-between">
        <div>
          <div className="font-mono text-xs text-ink-500 uppercase tracking-wider mb-1">
            WhatsApp
          </div>
          <h1 className="font-display text-4xl font-bold tracking-tight text-ink-900">
            Atendimento via WhatsApp
          </h1>
          <p className="text-ink-500 mt-1">
            Via Evolution API — auto-resposta com IA para seus contatos
          </p>
        </div>
        <button onClick={loadAll} className="btn-ghost" disabled={loading}>
          <RefreshCw size={14} /> Atualizar
        </button>
      </div>

      {/* Status card */}
      <div className="card p-6 mb-6">
        {loading ? (
          <div className="text-ink-400">Carregando...</div>
        ) : status?.configured ? (
          status.online ? (
            <StatusConnected status={status} onFetchQr={fetchQr} />
          ) : (
            <StatusOffline onCreate={createInstance} />
          )
        ) : (
          <StatusNotConfigured />
        )}
      </div>

      {qrCode && <QRCodeDisplay code={qrCode} onClose={() => setQrCode(null)} />}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-ink-100">
        <TabButton
          active={activeTab === "status"}
          onClick={() => setActiveTab("status")}
          icon={<Send size={14} />}
          label="Enviar mensagem"
        />
        <TabButton
          active={activeTab === "contacts"}
          onClick={() => setActiveTab("contacts")}
          icon={<MessageCircle size={14} />}
          label={`Contatos (${contacts.length})`}
        />
        <TabButton
          active={activeTab === "config"}
          onClick={() => setActiveTab("config")}
          icon={<Settings size={14} />}
          label="Configurações"
        />
      </div>

      {activeTab === "status" && (
        <SendMessageCard
          form={sendForm}
          setForm={setSendForm}
          onSend={sendMessage}
        />
      )}
      {activeTab === "contacts" && <ContactsList contacts={contacts} />}
      {activeTab === "config" && (
        <ConfigPanel config={config} onUpdate={updateConfig} />
      )}
    </div>
  );
}

function StatusConnected({
  status,
  onFetchQr,
}: {
  status: any;
  onFetchQr: () => void;
}) {
  const state = status.state?.instance?.state || status.state?.state;
  const isOpen = state === "open";

  return (
    <div className="flex items-start gap-4">
      <div
        className={`w-12 h-12 rounded-lg flex items-center justify-center ${
          isOpen ? "bg-signal-success/10" : "bg-signal-warning/10"
        }`}
      >
        {isOpen ? (
          <CheckCircle2 className="text-signal-success" size={24} />
        ) : (
          <QrCode className="text-signal-warning" size={24} />
        )}
      </div>
      <div className="flex-1">
        <h3 className="font-display font-semibold text-ink-900">
          {isOpen ? "Conectado" : "Aguardando QR Code"}
        </h3>
        <p className="text-sm text-ink-500 mt-0.5">
          Instância: <code className="font-mono">{status.instance}</code> · Estado:{" "}
          <code className="font-mono">{state || "desconhecido"}</code>
        </p>
        {!isOpen && (
          <button onClick={onFetchQr} className="btn-primary mt-3 text-xs">
            <QrCode size={14} /> Buscar QR Code
          </button>
        )}
      </div>
    </div>
  );
}

function StatusOffline({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex items-start gap-4">
      <div className="w-12 h-12 rounded-lg bg-signal-danger/10 flex items-center justify-center">
        <XCircle className="text-signal-danger" size={24} />
      </div>
      <div className="flex-1">
        <h3 className="font-display font-semibold text-ink-900">
          Evolution API não responde
        </h3>
        <p className="text-sm text-ink-500 mt-0.5">
          Verifique se o servidor está rodando no endereço configurado.
        </p>
        <button onClick={onCreate} className="btn-secondary mt-3 text-xs">
          Tentar criar instância
        </button>
      </div>
    </div>
  );
}

function StatusNotConfigured() {
  return (
    <div className="flex items-start gap-4">
      <div className="w-12 h-12 rounded-lg bg-ink-100 flex items-center justify-center">
        <Settings className="text-ink-400" size={24} />
      </div>
      <div className="flex-1">
        <h3 className="font-display font-semibold text-ink-900">
          Evolution API não configurada
        </h3>
        <p className="text-sm text-ink-500 mt-0.5">
          Configure <code className="font-mono">EVOLUTION_BASE_URL</code> e{" "}
          <code className="font-mono">EVOLUTION_API_KEY</code> no seu arquivo .env
          e reinicie o servidor.
        </p>
      </div>
    </div>
  );
}

function QRCodeDisplay({
  code,
  onClose,
}: {
  code: string;
  onClose: () => void;
}) {
  const imgSrc = code.startsWith("data:")
    ? code
    : `data:image/png;base64,${code}`;

  return (
    <div className="fixed inset-0 bg-ink-900/50 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
      <div className="bg-white rounded-lg p-8 max-w-md animate-slide-up">
        <h3 className="font-display text-xl font-semibold mb-4 text-center">
          Escaneie com seu WhatsApp
        </h3>
        <img
          src={imgSrc}
          alt="QR Code"
          className="w-full border border-ink-100 rounded-md"
        />
        <ol className="text-sm text-ink-600 mt-4 space-y-1">
          <li>1. Abra WhatsApp no celular</li>
          <li>2. Toque em Menu → Dispositivos Conectados</li>
          <li>3. Toque em &quot;Conectar dispositivo&quot;</li>
          <li>4. Aponte a câmera para este QR</li>
        </ol>
        <button onClick={onClose} className="btn-secondary w-full mt-4">
          Fechar
        </button>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
        active
          ? "text-ink-900 border-b-2 border-accent-400 -mb-px"
          : "text-ink-500 hover:text-ink-800"
      }`}
    >
      {icon} {label}
    </button>
  );
}

function SendMessageCard({
  form,
  setForm,
  onSend,
}: {
  form: { phone: string; message: string };
  setForm: (f: { phone: string; message: string }) => void;
  onSend: () => void;
}) {
  return (
    <div className="card p-6">
      <h3 className="font-display text-lg font-semibold text-ink-900 mb-4">
        Enviar mensagem manualmente
      </h3>
      <div className="space-y-3">
        <div>
          <label className="label">Telefone (com DDI, só números)</label>
          <input
            className="input font-mono"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="5521999999999"
          />
        </div>
        <div>
          <label className="label">Mensagem</label>
          <textarea
            className="input"
            rows={3}
            value={form.message}
            onChange={(e) => setForm({ ...form, message: e.target.value })}
            placeholder="Olá! Tudo bem?"
          />
        </div>
        <button
          onClick={onSend}
          disabled={!form.phone || !form.message}
          className="btn-primary"
        >
          <Send size={14} /> Enviar
        </button>
      </div>
    </div>
  );
}

function ContactsList({ contacts }: { contacts: WhatsAppContact[] }) {
  if (contacts.length === 0) {
    return (
      <div className="card p-8 text-center text-ink-400">
        Nenhum contato ainda. Contatos aparecem aqui assim que mandam a primeira
        mensagem.
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-ink-50 border-b border-ink-100">
          <tr>
            <th className="text-left px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
              Nome
            </th>
            <th className="text-left px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
              Telefone
            </th>
            <th className="text-left px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
              Msgs
            </th>
            <th className="text-left px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
              Última
            </th>
            <th className="text-right px-4 py-2 text-xs uppercase tracking-wider text-ink-500">
              Ações
            </th>
          </tr>
        </thead>
        <tbody>
          {contacts.map((c) => (
            <tr key={c.id} className="border-b border-ink-100 last:border-0">
              <td className="px-4 py-2.5">
                <div className="font-medium">{c.name || "—"}</div>
                {c.is_group ? (
                  <span className="badge-muted text-[10px]">grupo</span>
                ) : null}
              </td>
              <td className="px-4 py-2.5 font-mono text-xs">{c.phone}</td>
              <td className="px-4 py-2.5">{c.total_messages}</td>
              <td className="px-4 py-2.5 text-xs text-ink-500">
                {c.last_message_at
                  ? new Date(c.last_message_at).toLocaleString("pt-BR")
                  : "—"}
              </td>
              <td className="px-4 py-2.5 text-right">
                {c.is_blocked ? (
                  <span className="badge-muted">bloqueado</span>
                ) : (
                  <button className="btn-ghost text-xs">
                    <Ban size={12} />
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConfigPanel({
  config,
  onUpdate,
}: {
  config: Record<string, any>;
  onUpdate: (key: string, value: any) => void;
}) {
  const [local, setLocal] = useState(config);

  useEffect(() => {
    setLocal(config);
  }, [config]);

  return (
    <div className="card p-6 space-y-5">
      <ConfigToggle
        label="Auto-resposta ativada"
        hint="Quando desligado, o ClawVault recebe mas não responde automaticamente"
        value={local.enabled ?? true}
        onChange={(v) => {
          onUpdate("enabled", v);
          setLocal({ ...local, enabled: v });
        }}
      />
      <ConfigToggle
        label="Respeitar horário comercial"
        hint={`Responde só das ${local.business_hours_start || "08:00"} às ${local.business_hours_end || "20:00"}`}
        value={local.respect_business_hours ?? false}
        onChange={(v) => {
          onUpdate("respect_business_hours", v);
          setLocal({ ...local, respect_business_hours: v });
        }}
      />
      <ConfigToggle
        label="Saudação no primeiro contato"
        hint="Envia mensagem de boas-vindas quando recebe primeira mensagem"
        value={local.greeting_on_first_contact ?? true}
        onChange={(v) => {
          onUpdate("greeting_on_first_contact", v);
          setLocal({ ...local, greeting_on_first_contact: v });
        }}
      />
      <ConfigToggle
        label="Simular 'digitando'"
        hint="Melhora a percepção humana antes de enviar resposta"
        value={local.typing_before_reply ?? true}
        onChange={(v) => {
          onUpdate("typing_before_reply", v);
          setLocal({ ...local, typing_before_reply: v });
        }}
      />
      <ConfigToggle
        label="Responder em grupos"
        hint="Cuidado: pode gerar muitas mensagens. Desligado por padrão."
        value={local.auto_reply_groups ?? false}
        onChange={(v) => {
          onUpdate("auto_reply_groups", v);
          setLocal({ ...local, auto_reply_groups: v });
        }}
      />
    </div>
  );
}

function ConfigToggle({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <div className="font-medium text-ink-900 text-sm">{label}</div>
        <div className="text-xs text-ink-500 mt-0.5">{hint}</div>
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`relative w-11 h-6 rounded-full transition-colors ${
          value ? "bg-accent-400" : "bg-ink-200"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
            value ? "translate-x-5" : ""
          }`}
        />
      </button>
    </div>
  );
}
