"use client";

import { useState, useEffect } from "react";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-2 text-xs text-ink-500 hover:text-ink-700 dark:text-ink-400 dark:hover:text-ink-200 transition-colors"
      title={dark ? "Modo claro" : "Modo escuro"}
    >
      {dark ? <Sun size={14} /> : <Moon size={14} />}
      <span className="font-mono">{dark ? "Claro" : "Escuro"}</span>
    </button>
  );
}
