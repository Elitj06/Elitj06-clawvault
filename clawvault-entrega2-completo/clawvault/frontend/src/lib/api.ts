/**
 * Cliente da API ClawVault
 * =========================
 * Wrapper simples para todas as chamadas ao backend FastAPI.
 * Todas as páginas importam daqui para manter consistência.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API ${res.status}: ${error}`);
  }

  return res.json();
}

// =========================================================================
// TYPES
// =========================================================================

export interface SystemStatus {
  version: string;
  providers: Record<string, boolean>;
  budget: {
    spent_usd: number;
    limit_usd: number;
    percent_used: number;
  };
  stats: {
    conversations: number;
    messages: number;
    agents: number;
  };
}

export interface ModelInfo {
  id: string;
  provider: string;
  tier: string;
  context_window: number;
  cost_input: number;
  cost_output: number;
  supports_vision: boolean;
  description: string;
  available: boolean;
}

export interface Agent {
  id: number;
  name: string;
  role: string;
  parent_agent: string | null;
  is_main: number;
  preferred_model: string | null;
  total_calls: number;
  total_tokens: number;
  created_at: string;
}

export interface AgentMemoryStats {
  core: { entries: number; tokens: number };
  learned: { entries: number; tokens: number };
  episodic: { entries: number; tokens: number };
}

export interface Conversation {
  id: number;
  uuid: string;
  title: string;
  agent_name: string;
  created_at: string;
  updated_at: string;
  total_tokens: number;
  total_cost_usd: number;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  role: string;
  content: string;
  model_used: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  created_at: string;
}

export interface UsageByModel {
  model_id: string;
  provider: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  total_cost: number;
}

export interface UsageDaily {
  day: string;
  calls: number;
  cost: number;
  tokens: number;
}

export interface VaultNode {
  id: string;
  label: string;
}

export interface VaultEdge {
  source: string;
  target: string;
}

export interface WhatsAppContact {
  id: number;
  remote_jid: string;
  phone: string;
  name: string | null;
  is_group: number;
  is_blocked: number;
  conversation_id: number;
  last_message_at: string;
  total_messages: number;
}

// =========================================================================
// ENDPOINTS
// =========================================================================

export const api = {
  // Status
  getStatus: () => request<SystemStatus>("/api/status"),

  // Models
  getModels: (availableOnly = false) =>
    request<{ models: ModelInfo[]; total: number }>(
      `/api/models${availableOnly ? "?available_only=true" : ""}`
    ),

  // Conversations & Chat
  listConversations: (limit = 50) =>
    request<{ conversations: Conversation[] }>(
      `/api/conversations?limit=${limit}`
    ),
  getMessages: (id: number) =>
    request<{ messages: ChatMessage[] }>(`/api/conversations/${id}/messages`),
  sendChat: (data: {
    message: string;
    conversation_id?: number;
    agent_name?: string;
    model_override?: string;
    compress?: boolean;
  }) =>
    request<{
      content: string;
      model_id: string;
      provider: string;
      input_tokens: number;
      output_tokens: number;
      cost_usd: number;
      complexity: string | null;
      conversation_id: number;
      compression_savings: number;
    }>("/api/chat", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Agents
  listAgents: () => request<{ agents: Agent[] }>("/api/agents"),
  getAgent: (name: string) =>
    request<{
      agent: Agent;
      memory_stats: AgentMemoryStats;
      subagents: Agent[];
    }>(`/api/agents/${name}`),
  createAgent: (data: {
    name: string;
    role: string;
    parent_agent?: string;
    preferred_model?: string;
    system_prompt?: string;
  }) =>
    request<{ status: string }>("/api/agents", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getAgentMemory: (name: string) =>
    request<{ core: any[]; learned: any[]; episodic: any[] }>(
      `/api/agents/${name}/memory`
    ),

  // Shared memory
  listChannels: () =>
    request<{ channels: any[] }>("/api/shared-memory/channels"),
  shareMemory: (data: {
    namespace: string;
    key: string;
    content: string;
    source_agent?: string;
  }) =>
    request<{ status: string }>("/api/shared-memory", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Vault
  vaultStatus: () => request<Record<string, any>>("/api/vault/status"),
  vaultSearch: (q: string) =>
    request<{ results: any[] }>(`/api/vault/search?q=${encodeURIComponent(q)}`),
  vaultGraph: () =>
    request<{ nodes: VaultNode[]; edges: VaultEdge[] }>("/api/vault/graph"),
  vaultEntities: () => request<Record<string, string[]>>("/api/vault/entities"),
  saveNote: (data: {
    title: string;
    content: string;
    layer?: string;
    category?: string;
    tags?: string[];
  }) =>
    request<{ status: string; path: string }>("/api/vault/notes", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Usage
  getBudget: () => request<any>("/api/usage/budget"),
  usageByModel: (days = 30) =>
    request<{ usage: UsageByModel[]; days: number }>(
      `/api/usage/by-model?days=${days}`
    ),
  usageDaily: (days = 30) =>
    request<{ daily: UsageDaily[]; days: number }>(
      `/api/usage/daily?days=${days}`
    ),

  // WhatsApp
  whatsappStatus: () => request<any>("/api/whatsapp/status"),
  whatsappConfig: () => request<Record<string, any>>("/api/whatsapp/config"),
  updateWhatsappConfig: (key: string, value: any) =>
    request<{ status: string }>("/api/whatsapp/config", {
      method: "PUT",
      body: JSON.stringify({ key, value }),
    }),
  createWhatsappInstance: () =>
    request<any>("/api/whatsapp/instance/create", { method: "POST" }),
  getQrcode: () => request<any>("/api/whatsapp/qrcode"),
  listContacts: () =>
    request<{ contacts: WhatsAppContact[] }>("/api/whatsapp/contacts"),
  sendWhatsappMessage: (phone: string, message: string) =>
    request<{ status: string }>("/api/whatsapp/send", {
      method: "POST",
      body: JSON.stringify({ phone, message }),
    }),
};

export function wsUrl(path: string): string {
  const base = API_URL.replace(/^http/, "ws");
  return `${base}${path}`;
}
