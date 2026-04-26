"use client";

/**
 * Chat page with SSE streaming (P4) + dark mode + conversation history + cursor fix
 * Merged from original chat page (dark mode, sidebar integration, focus management)
 * with P4 streaming SSE support.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Send, Loader2, Sparkles, Zap, DollarSign, Hash, Paperclip, Image, Mic, X } from "lucide-react";
import { api } from "@/lib/api";
import {
  getSelectedConversationId,
  onConversationSelected,
} from "@/components/Sidebar";

const API_URL = ""; // Use Next.js rewrite proxy (/api → backend:8000)

interface FileAttachment {
  name: string;
  type: string; // "image" | "audio" | "file"
  dataUrl: string;
  size: number;
}

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
  attachments?: FileAttachment[];
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
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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
  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files) return;

    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        let type: FileAttachment["type"] = "file";
        if (file.type.startsWith("image/")) type = "image";
        else if (file.type.startsWith("audio/")) type = "audio";

        setAttachments((prev) => [...prev, {
          name: file.name,
          type,
          dataUrl,
          size: file.size,
        }]);
      };
      reader.readAsDataURL(file);
    });

    // Reset input so same file can be re-selected
    e.target.value = "";
  }

  function removeAttachment(index: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  }

  async function send() {
    const text = input.trim();
    if ((!text && attachments.length === 0) || sending) return;

    setError(null);
    setSending(true);

    // Build message text including attachment descriptions
    let messageText = text;
    const currentAttachments = [...attachments];
    if (currentAttachments.length > 0) {
      const fileDescs = currentAttachments.map((a) => {
        if (a.type === "image") return `[Imagem: ${a.name}]`;
        if (a.type === "audio") return `[Áudio: ${a.name}]`;
        return `[Arquivo: ${a.name}]`;
      });
      messageText = fileDescs.join("\n") + (text ? "\n" + text : "");
    }

    setInput("");
    setAttachments([]);
    setStatusText("Enviando...");

    // Add user message immediately
    const userMsgId = `u-${Date.now()}`;
    const assistantMsgId = `a-${Date.now()}`;
    setMessages((m) => [
      ...m,
      { id: userMsgId, role: "user", content: messageText, attachments: currentAttachments.length > 0 ? currentAttachments : undefined },
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
    <div className="h-[calc(100vh-7rem)] lg:h-[calc(100vh-4rem)] flex flex-col animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 sm:mb-6 gap-3">
        <div>
          <div className="font-mono text-xs text-ink-500 dark:text-ink-400 uppercase tracking-wider mb-1">
            Chat
          </div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink-900 dark:text-ink-50">
            Conversar com agente
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {totalCost > 0 && (
            <div className="text-xs sm:text-sm font-mono text-ink-600 dark:text-ink-400">
              Custo: ${totalCost.toFixed(6)}
            </div>
          )}
          <button
            onClick={newConversation}
            className="btn-secondary text-xs whitespace-nowrap"
            disabled={sending}
          >
            Nova conversa
          </button>
        </div>
      </div>

      {/* Controls bar */}
      <div className="card p-3 mb-3 sm:mb-4 flex flex-wrap items-center gap-3 sm:gap-4">
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
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 px-1 sm:pr-2">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center px-4">
            <div className="w-14 h-14 rounded-full bg-accent-50 dark:bg-accent-900/30 flex items-center justify-center mb-3">
              <Sparkles className="text-accent-400" size={24} />
            </div>
            <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-ink-50 mb-2">
              Comece uma conversa
            </h3>
            <p className="text-ink-500 dark:text-ink-400 text-sm max-w-sm">
              Anexe fotos, áudios ou prints. O sistema escolhe o melhor modelo automaticamente.
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

      {/* Attachments preview */}
      {attachments.length > 0 && (
        <div className="flex gap-2 px-3 py-2 overflow-x-auto">
          {attachments.map((att, i) => (
            <div key={i} className="relative shrink-0 group">
              {att.type === "image" ? (
                <div className="w-16 h-16 rounded-lg border border-ink-200 dark:border-ink-700 overflow-hidden">
                  <img src={att.dataUrl} alt={att.name} className="w-full h-full object-cover" />
                </div>
              ) : (
                <div className="w-16 h-16 rounded-lg border border-ink-200 dark:border-ink-700 bg-ink-50 dark:bg-ink-800 flex flex-col items-center justify-center p-1">
                  {att.type === "audio" ? <Mic size={16} className="text-ink-400" /> : <Paperclip size={16} className="text-ink-400" />}
                  <span className="text-[8px] text-ink-400 truncate w-full text-center mt-0.5">{att.name}</span>
                </div>
              )}
              <button
                onClick={() => removeAttachment(i)}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="card p-2 sm:p-3 focus-within:border-accent-300 transition-colors">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,audio/*,.pdf,.txt,.md,.csv,.json"
          multiple
          className="hidden"
          onChange={handleFileSelect}
        />
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Digite sua mensagem..."
          className="w-full resize-none bg-transparent focus:outline-none text-sm placeholder:text-ink-400 text-ink-900 dark:text-ink-100"
          rows={2}
          readOnly={sending}
        />
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={sending}
              className="p-1.5 rounded-md hover:bg-ink-100 dark:hover:bg-ink-800 text-ink-400 hover:text-ink-600 dark:hover:text-ink-300 transition-colors disabled:opacity-40"
              title="Anexar arquivo"
            >
              <Paperclip size={16} />
            </button>
            <div className="text-xs text-ink-400 dark:text-ink-500 font-mono">
              {input.length > 0 ? `${input.length} chars` : ""}
            </div>
          </div>
          <button
            onClick={send}
            disabled={(!input.trim() && attachments.length === 0) || sending}
            className="btn-primary text-xs sm:text-sm disabled:opacity-40"
          >
            {sending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Send size={14} />
            )}
            <span className="hidden sm:inline">Enviar</span>
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
        <div className="max-w-[85%] sm:max-w-2xl bg-ink-900 dark:bg-accent-400 text-ink-50 dark:text-ink-900 rounded-lg rounded-br-sm px-3 sm:px-4 py-2.5 text-sm">
          {/* Show attachments */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {message.attachments.map((att, i) => (
                att.type === "image" ? (
                  <div key={i} className="w-20 h-20 rounded-md overflow-hidden border border-white/20">
                    <img src={att.dataUrl} alt={att.name} className="w-full h-full object-cover" />
                  </div>
                ) : (
                  <div key={i} className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-white/10 text-[10px]">
                    {att.type === "audio" ? <Mic size={10} /> : <Paperclip size={10} />}
                    {att.name}
                  </div>
                )
              ))}
            </div>
          )}
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
      <div className="max-w-[85%] sm:max-w-2xl">
        <div className="bg-white dark:bg-ink-800 border border-ink-100 dark:border-ink-700 rounded-lg rounded-bl-sm px-3 sm:px-4 py-3 text-sm text-ink-800 dark:text-ink-200 whitespace-pre-wrap">
          {message.content}
          {message.streaming && (
            <span className="inline-block w-2 h-4 bg-current opacity-50 ml-1 animate-pulse align-middle rounded-sm" />
          )}
        </div>
        {!message.streaming && (message.model || message.cost) && (
          <div className="flex flex-wrap items-center gap-2 sm:gap-3 mt-1.5 px-1 text-[10px] font-mono text-ink-400 dark:text-ink-500">
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
