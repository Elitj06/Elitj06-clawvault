"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  Users,
  Database,
  MessageCircle,
  BarChart3,
  Settings,
  Clock,
  Menu,
  X,
} from "lucide-react";
import { api, type Conversation } from "@/lib/api";
import { ThemeToggle } from "./ThemeToggle";

const NAV_ITEMS = [
  { href: "/", label: "Visão geral", icon: LayoutDashboard },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/agents", label: "Agentes", icon: Users },
  { href: "/vault", label: "Vault", icon: Database },
  { href: "/whatsapp", label: "WhatsApp", icon: MessageCircle },
  { href: "/usage", label: "Uso e custos", icon: BarChart3 },
  { href: "/settings", label: "Configurações", icon: Settings },
];

// Shared state for selected conversation
let _selectedConversationId: number | null = null;
let _onConversationSelected: ((id: number | null) => void) | null = null;

export function setSelectedConversationId(id: number | null) {
  _selectedConversationId = id;
  _onConversationSelected?.(id);
}

export function getSelectedConversationId() {
  return _selectedConversationId;
}

export function onConversationSelected(cb: (id: number | null) => void) {
  _onConversationSelected = cb;
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);

  useEffect(() => {
    api.listConversations(10).then((d) => setConversations(d.conversations)).catch(() => {});
  }, []);

  // Close sidebar on route change (mobile)
  useEffect(() => {
    onClose();
  }, [pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  function openConversation(id: number) {
    setSelectedConversationId(id);
    router.push("/chat");
  }

  return (
    <>
      {/* Backdrop overlay - mobile only */}
      {open && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`
          w-64 fixed left-0 top-0 h-screen bg-white dark:bg-ink-900 border-r border-ink-100 dark:border-ink-800 flex flex-col z-50
          transition-transform duration-300 ease-in-out
          lg:translate-x-0
          ${open ? "translate-x-0" : "-translate-x-full"}
        `}
      >
      {/* Logo */}
      <div className="px-6 py-6 border-b border-ink-100 dark:border-ink-800">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-ink-900 dark:bg-ink-100 flex items-center justify-center">
            <span className="text-accent-300 text-lg">🐾</span>
          </div>
          <div>
            <div className="font-display font-bold text-lg tracking-tight text-ink-900 dark:text-ink-50">
              ClawVault
            </div>
            <div className="font-mono text-[10px] text-ink-400 -mt-0.5">
              v0.2.0
            </div>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);

          return (
            <Link
              key={href}
              href={href}
              className={isActive ? "nav-link-active" : "nav-link"}
            >
              <Icon size={16} strokeWidth={2} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Recent conversations */}
      {conversations.length > 0 && (
        <div className="flex-1 overflow-y-auto px-3 pb-2">
          <div className="flex items-center gap-1.5 px-3 pt-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-400 dark:text-ink-500">
            <Clock size={10} />
            Conversas recentes
          </div>
          <div className="space-y-0.5">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => openConversation(conv.id)}
                className="w-full text-left px-3 py-1.5 rounded-md text-xs hover:bg-ink-100 dark:hover:bg-ink-800 transition-colors"
              >
                <div className="font-medium text-ink-700 dark:text-ink-300 truncate">
                  {conv.title || `Conversa #${conv.id}`}
                </div>
                <div className="text-[10px] text-ink-400 font-mono">
                  {new Date(conv.updated_at).toLocaleDateString("pt-BR", {
                    day: "2-digit",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Close button - mobile only */}
      <button
        onClick={onClose}
        className="absolute top-4 right-3 p-1 rounded-md hover:bg-ink-100 dark:hover:bg-ink-800 lg:hidden"
        aria-label="Fechar menu"
      >
        <X size={18} />
      </button>

      {/* Footer: Theme + Status */}
      <div className="px-4 py-4 border-t border-ink-100 dark:border-ink-800 space-y-2">
        <ThemeToggle />
        <StatusIndicator />
      </div>
    </aside>
    </>
  );
}

// Hamburger button for mobile header
export function HamburgerButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="lg:hidden p-2 rounded-md hover:bg-ink-100 dark:hover:bg-ink-800 transition-colors"
      aria-label="Abrir menu"
    >
      <Menu size={20} />
    </button>
  );
}

function StatusIndicator() {
  return (
    <div className="flex items-center gap-2 text-xs text-ink-500 dark:text-ink-400">
      <span className="relative flex h-2 w-2">
        <span className="animate-pulse-slow absolute inline-flex h-full w-full rounded-full bg-signal-success opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-signal-success" />
      </span>
      <span className="font-mono">API online</span>
    </div>
  );
}
