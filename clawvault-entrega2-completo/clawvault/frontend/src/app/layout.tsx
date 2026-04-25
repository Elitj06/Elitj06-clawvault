import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "ClawVault — Dashboard",
  description: "Sistema de agentes multi-LLM com memória persistente",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('theme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme:dark)').matches)){document.documentElement.classList.add('dark')}}catch(e){}})()`,
          }}
        />
      </head>
      <body className="bg-ink-50 dark:bg-ink-950 text-ink-900 dark:text-ink-100 min-h-screen">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 ml-64">
            <div className="max-w-7xl mx-auto px-8 py-8">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
