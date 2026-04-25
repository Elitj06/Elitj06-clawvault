"use client";

import { useState, useCallback } from "react";
import { Sidebar, HamburgerButton } from "@/components/Sidebar";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  return (
    <>
      <Sidebar open={sidebarOpen} onClose={closeSidebar} />

      {/* Mobile top bar */}
      <header className="lg:hidden fixed top-0 left-0 right-0 z-30 h-14 bg-white dark:bg-ink-900 border-b border-ink-100 dark:border-ink-800 flex items-center px-3 gap-3">
        <HamburgerButton onClick={() => setSidebarOpen(true)} />
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-ink-900 dark:bg-ink-100 flex items-center justify-center">
            <span className="text-accent-300 text-sm">🐾</span>
          </div>
          <span className="font-display font-bold text-sm">ClawVault</span>
        </div>
      </header>

      {/* Main content */}
      <main className="lg:ml-64 pt-14 lg:pt-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
          {children}
        </div>
      </main>
    </>
  );
}
