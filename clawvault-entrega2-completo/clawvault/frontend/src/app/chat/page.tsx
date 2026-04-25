"use client";

/**
 * Chat page with SSE streaming (P4) + dark mode + conversation history + cursor fix
 * Merged from original chat page (dark mode, sidebar integration, focus management)
 * with P4 streaming SSE support.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Send, Loader2, Sparkles, Zap, DollarSign, Hash } from "lucide-react";
import { api } from "@/lib/api";
import {
  getSelectedConversationId,
  onConversationSelected,
} from "@/components/Sidebar";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  model?: string;
  cost?: number;
  tokensIn?: number;
  tokensOut?: number;
  complexity?: string;
  compressionSaved?: number;
  streaming?: boolean;
}

interface Agent {
  name: string;
  role: string;
  is_main: number;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState("main");
  const [compress, setCompress] = useState(true);
  const [totalCost, setTotalCost] = useState(0);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load agents on mount
  useEffect(() => {
    api.listAgents().then((d) => setAgents(d.agents));
  }, []);

  // Focus textarea on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Refocus textarea when sending completes
  useEffect(() => {
    if (!sending) {
      const timer = setTimeout(() => textareaRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [sending]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Listen for conversation selection from sidebar
  const loadConversation = useCallback(async (id: number) => {
    try {
      const data = await api.getMessages(id);
      const loaded: Message[] = data.messages.map((m: any) => ({
        id: `loaded-${m.id}`,
        role: m.role as Message["role"],
        content: m.content,
        model: m.model_used || undefined,
        cost: m.cost_usd || undefined,
        tokensIn: m.input_tokens || undefined,
        tokensOut: m.output_tokens || undefined,
      }));
      setMessages(loaded);
      setConversationId(id);
      setTotalCost(
        data.messages.reduce((sum: number, m: any) => sum + (m.cost_usd || 0), 0)
      );
    } catch (e) {
      console.error("Failed to load conversation:", e);
    }
  }, []);

  useEffect(() => {
    const preselected = getSelectedConversationId();
    if (preselected) {
      loadConversation(preselected);
    }
    onConversationSelected((id) => {
      if (id) {
        loadConversation(id);
      }
    });
  }, [loadConversation]);

  // -------------------------------------------------------------------------
  // SSE parser
  // -------------------------------------------------------------------------
  function parseSseEvent(
    raw: string
  ): { event: string; data: Record<string, unknown> } | null {
    const lines = raw.split("\n");
    let eventName = "message";
    let data = "";
    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        data += line.slice(5).trim();
      }
    }
    if (!data) return null;
    try {
      return { event: eventName, data: JSON.parse(data) };
    } catch {
      return null;
    }
  }

  // -------------------------------------------------------------------------
  // Send with streaming SSE
  // -------------------------------------------------------------------------
  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    setError(null);
    setSending(true);
    setInput("");
    setStatusText("Enviando...");

    // Add user message immediately
    const userMsgId = `u-${Date.now()}`;
    const assistantMsgId = `a-${Date.now()}`;
    setMessages((m) => [
      ...m,
      { id: userMsgId, role: "user", content: text },
      {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        streaming: true,
      },
    ]);

    setTimeout(() => textareaRef.current?.focus(), 0);

    // Abort previous request if any
    abortControllerRef.current?.abort();
    const ctrl = new AbortController();
    abortControllerRef.current = ctrl;

    try {
      const res = await fetch(`${API_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId || undefined,
          agent_name: selectedAgent,
          compress,
        }),
        signal: ctrl.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const evt of events) {
          if (!evt.trim()) continue;
          const parsed = parseSseEvent(evt);
          if (!parsed) continue;

          const { event: eventName, data } = parsed;

          if (eventName === "meta") {
            if (typeof data.conversation_id === "number") {
              setConversationId(data.conversation_id);
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      model: data.model as string,
                      complexity: data.complexity as string,
                    }
                  : m
              )
            );
            setStatusText("Gerando resposta...");
          } else if (eventName === "delta") {
            const chunk = (data.text as string) || "";
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: m.content + chunk }
                  : m
              )
            );
          } else if (eventName === "done") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      streaming: false,
                      cost: data.cost_usd as number,
                      tokensIn: data.input_tokens as number,
                      tokensOut: data.output_tokens as number,
                      compressionSaved: data.compression_savings as number,
                    }
                  : m
              )
            );
            if (typeof data.cost_usd === "number") {
              setTotalCost((c) => c + (data.cost_usd as number));
            }
          } else if (eventName === "error") {
            const errMsg = (data.error as string) || "erro desconhecido";
            setError(errMsg);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: `Erro: ${errMsg}`, streaming: false }
                  : m
              )
            );
          }
        }
      }
    } catch (e: unknown) {
      const aborted = e instanceof Error && e.name === "AbortError";
      if (!aborted) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, content: `Erro: ${msg}`, streaming: false }
              : m
          )
        );
      }
    } finally {
      setSending(false);
      setStatusText(null);
      setTimeout(() => textareaRef.current?.focus(), 0);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function newConversation() {
    setMessages([]);
    setConversationId(null);
    setTotalCost(0);
    setError(null);
    setTimeout(() => textareaRef.current?.focus(), 0);
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="font-mono text-xs text-ink-500 dark:text-ink-400 uppercase tracking-wider mb-1">
            Chat
          </div>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink-900 dark:text-ink-50">
            Conversar com agente
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {totalCost > 0 && (
            <div className="text-sm font-mono text-ink-600 dark:text-ink-400">
              Custo: ${totalCost.toFixed(6)}
            </div>
          )}
          <button
            onClick={newConversation}
            className="btn-secondary text-xs"
            disabled={sending}
          >
            Nova conversa
          </button>
        </div>
      </div>

      {/* Controls bar */}
      <div className="card p-3 mb-4 flex items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-ink-600 dark:text-ink-400">Agente:</label>
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="text-sm px-2 py-1 border border-ink-200 dark:border-ink-700 rounded bg-white dark:bg-ink-800 text-ink-900 dark:text-ink-100 font-mono"
            disabled={sending}
          >
            {agents.map((a) => (
              <option key={a.name} value={a.name}>
                {a.is_main ? "★ " : ""}
                {a.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs font-medium text-ink-600 dark:text-ink-400 cursor-pointer">
            <input
              type="checkbox"
              checked={compress}
              onChange={(e) => setCompress(e.target.checked)}
              className="accent-accent-400"
            />
            Compressão
          </label>
        </div>

        {conversationId && (
          <div className="ml-auto text-xs text-ink-500 dark:text-ink-500 font-mono">
            conversa #{conversationId}
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-2">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 rounded-full bg-accent-50 dark:bg-accent-900/30 flex items-center justify-center mb-4">
              <Sparkles className="text-accent-400" size={28} />
            </div>
            <h3 className="font-display text-xl font-semibold text-ink-900 dark:text-ink-50 mb-2">
              Comece uma conversa
            </h3>
            <p className="text-ink-500 dark:text-ink-400 text-sm max-w-sm">
              O sistema vai classificar sua pergunta e escolher o modelo mais
              econômico automaticamente. Respostas via streaming SSE.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {error && (
          <div className="max-w-xl mx-auto bg-signal-danger/10 border border-signal-danger/20 text-signal-danger rounded-md px-3 py-2 text-xs text-center font-mono animate-slide-up">
            {error}
          </div>
        )}

        {statusText && (
          <div className="flex items-center gap-2 text-xs text-ink-500 dark:text-ink-400 animate-fade-in">
            <Loader2 size={12} className="animate-spin" />
            {statusText}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="card p-3 focus-within:border-accent-300 transition-colors">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Digite sua mensagem (Enter para enviar, Shift+Enter para nova linha)"
          className="w-full resize-none bg-transparent focus:outline-none text-sm placeholder:text-ink-400 text-ink-900 dark:text-ink-100"
          rows={2}
          readOnly={sending}
        />
        <div className="flex items-center justify-between mt-2">
          <div className="text-xs text-ink-400 dark:text-ink-500 font-mono">
            {input.length > 0 ? `${input.length} caracteres` : ""}
          </div>
          <button
            onClick={send}
            disabled={!input.trim() || sending}
            className="btn-primary text-sm disabled:opacity-40"
          >
            {sending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Send size={14} />
            )}
            Enviar
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-slide-up">
        <div className="max-w-2xl bg-ink-900 dark:bg-accent-400 text-ink-50 dark:text-ink-900 rounded-lg rounded-br-sm px-4 py-2.5 text-sm">
          {message.content}
        </div>
      </div>
    );
  }

  if (message.role === "system") {
    return (
      <div className="max-w-xl mx-auto bg-signal-danger/10 border border-signal-danger/20 text-signal-danger rounded-md px-3 py-2 text-xs text-center font-mono animate-slide-up">
        {message.content}
      </div>
    );
  }

  // Assistant message
  return (
    <div className="flex justify-start animate-slide-up">
      <div className="max-w-2xl">
        <div className="bg-white dark:bg-ink-800 border border-ink-100 dark:border-ink-700 rounded-lg rounded-bl-sm px-4 py-3 text-sm text-ink-800 dark:text-ink-200 whitespace-pre-wrap">
          {message.content}
          {message.streaming && (
            <span className="inline-block w-2 h-4 bg-current opacity-50 ml-1 animate-pulse align-middle rounded-sm" />
          )}
        </div>
        {!message.streaming && (message.model || message.cost) && (
          <div className="flex items-center gap-3 mt-1.5 px-1 text-[10px] font-mono text-ink-400 dark:text-ink-500">
            {message.model && (
              <span className="flex items-center gap-1">
                <Sparkles size={10} />
                {message.model}
              </span>
            )}
            {message.complexity && (
              <span className="flex items-center gap-1">
                <Zap size={10} />
                {message.complexity}
              </span>
            )}
            {message.cost !== undefined && (
              <span className="flex items-center gap-1">
                <DollarSign size={10} />${message.cost.toFixed(6)}
              </span>
            )}
            {message.tokensOut !== undefined && (
              <span className="flex items-center gap-1">
                <Hash size={10} />
                {message.tokensIn}/{message.tokensOut}
              </span>
            )}
            {(message.compressionSaved || 0) > 0 && (
              <span className="text-accent-600 dark:text-accent-400">
                −{message.compressionSaved} tok
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
