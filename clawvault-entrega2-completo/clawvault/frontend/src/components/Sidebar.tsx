"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  Users,
  Database,
  MessageCircle,
  BarChart3,
  Settings,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Visão geral", icon: LayoutDashboard },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/agents", label: "Agentes", icon: Users },
  { href: "/vault", label: "Vault", icon: Database },
  { href: "/whatsapp", label: "WhatsApp", icon: MessageCircle },
  { href: "/usage", label: "Uso e custos", icon: BarChart3 },
  { href: "/settings", label: "Configurações", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 fixed left-0 top-0 h-screen bg-white border-r border-ink-100 flex flex-col">
      {/* Logo */}
      <div className="px-6 py-6 border-b border-ink-100">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-ink-900 flex items-center justify-center">
            <span className="text-accent-300 text-lg">🐾</span>
          </div>
          <div>
            <div className="font-display font-bold text-lg tracking-tight text-ink-900">
              ClawVault
            </div>
            <div className="font-mono text-[10px] text-ink-400 -mt-0.5">
              v0.2.0
            </div>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
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

      {/* Status */}
      <div className="px-4 py-4 border-t border-ink-100">
        <StatusIndicator />
      </div>
    </aside>
  );
}

function StatusIndicator() {
  return (
    <div className="flex items-center gap-2 text-xs text-ink-500">
      <span className="relative flex h-2 w-2">
        <span className="animate-pulse-slow absolute inline-flex h-full w-full rounded-full bg-signal-success opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-signal-success" />
      </span>
      <span className="font-mono">API online</span>
    </div>
  );
}
