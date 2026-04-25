import type { Metadata, Viewport } from "next";
import "./globals.css";
import { LayoutShell } from "@/components/LayoutShell";

export const metadata: Metadata = {
  title: "ClawVault — Dashboard",
  description: "Sistema de agentes multi-LLM com memória persistente",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
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
          <LayoutShell>{children}</LayoutShell>
        </div>
      </body>
    </html>
  );
}
