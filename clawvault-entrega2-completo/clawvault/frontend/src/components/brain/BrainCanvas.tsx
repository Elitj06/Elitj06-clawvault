"use client";

/**
 * BrainCanvas — Cérebro pulsante do Vault
 * ========================================
 * Renderiza notas do vault como um cérebro orgânico pulsando.
 * Cada nota = neurônio (nó), cada [[wiki-link]] = sinapse (aresta).
 * Sinapses disparam pulsos elétricos entre neurônios conectados.
 *
 * Usa Canvas 2D puro (sem libs externas) pra performance máxima.
 * Responsivo e touch-friendly.
 */

import { useEffect, useRef, useCallback, useState } from "react";

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

interface BrainNode {
  id: string;
  label: string;
  category: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  connections: number;
  pulsePhase: number;
}

interface BrainEdge {
  source: string;
  target: string;
  pulseProgress: number;
  pulseSpeed: number;
}

interface GraphData {
  nodes: { id: string; label: string; category?: string }[];
  edges: { source: string; target: string }[];
}

interface BrainCanvasProps {
  data: GraphData;
  onNodeClick?: (nodeId: string) => void;
  className?: string;
}

// ---------------------------------------------------------------------------
// Cores por categoria
// ---------------------------------------------------------------------------

const CATEGORY_COLORS: Record<string, string> = {
  project: "#F59E0B",   // amarelo
  projects: "#F59E0B",
  pessoa: "#EF4444",    // coral
  people: "#EF4444",
  conceito: "#3B82F6",  // azul
  concept: "#3B82F6",
  empresa: "#10B981",   // verde
  company: "#10B981",
  evento: "#8B5CF6",    // roxo
  event: "#8B5CF6",
  output: "#F97316",    // dourado
  agente: "#06B6D4",    // ciano
  agent: "#06B6D4",
  skill: "#EC4899",     // rosa
  memória: "#94A3B8",   // cinza
  memory: "#94A3B8",
  default: "#94A3B8",   // cinza
};

const CATEGORY_GLOW: Record<string, string> = {
  project: "rgba(245,158,11,0.3)",
  projects: "rgba(245,158,11,0.3)",
  pessoa: "rgba(239,68,68,0.3)",
  people: "rgba(239,68,68,0.3)",
  conceito: "rgba(59,130,246,0.3)",
  concept: "rgba(59,130,246,0.3)",
  empresa: "rgba(16,185,129,0.3)",
  company: "rgba(16,185,129,0.3)",
  evento: "rgba(139,92,246,0.3)",
  event: "rgba(139,92,246,0.3)",
  default: "rgba(148,163,184,0.2)",
};

function getCategoryColor(cat?: string): string {
  if (!cat) return CATEGORY_COLORS.default;
  const lower = cat.toLowerCase();
  for (const [key, color] of Object.entries(CATEGORY_COLORS)) {
    if (lower.includes(key)) return color;
  }
  return CATEGORY_COLORS.default;
}

function getCategoryGlow(cat?: string): string {
  if (!cat) return CATEGORY_GLOW.default;
  const lower = cat.toLowerCase();
  for (const [key, glow] of Object.entries(CATEGORY_GLOW)) {
    if (lower.includes(key)) return glow;
  }
  return CATEGORY_GLOW.default;
}

// ---------------------------------------------------------------------------
// Detecção de categoria pelo path da nota
// ---------------------------------------------------------------------------

function detectCategory(path: string): string {
  const lower = path.toLowerCase();
  if (lower.includes("project") || lower.includes("projeto")) return "project";
  if (lower.includes("pessoa") || lower.includes("people")) return "pessoa";
  if (lower.includes("concept") || lower.includes("conceito")) return "conceito";
  if (lower.includes("empresa") || lower.includes("company")) return "empresa";
  if (lower.includes("event") || lower.includes("evento")) return "evento";
  if (lower.includes("output")) return "output";
  if (lower.includes("agent")) return "agente";
  if (lower.includes("skill")) return "skill";
  if (lower.includes("fatos") || lower.includes("fact")) return "memória";
  return "default";
}

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

export default function BrainCanvas({ data, onNodeClick, className }: BrainCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const nodesRef = useRef<BrainNode[]>([]);
  const edgesRef = useRef<BrainEdge[]>([]);
  const [focusedNode, setFocusedNode] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [zenMode, setZenMode] = useState(false);
  const mouseRef = useRef({ x: 0, y: 0, down: false, dragNode: null as string | null });

  // Inicializar nós e arestas a partir dos dados
  useEffect(() => {
    if (!data || !data.nodes) return;

    const w = canvasRef.current?.width || 800;
    const h = canvasRef.current?.height || 600;
    const cx = w / 2;
    const cy = h / 2;

    // Contar conexões por nó
    const connCount: Record<string, number> = {};
    for (const e of data.edges) {
      connCount[e.source] = (connCount[e.source] || 0) + 1;
      connCount[e.target] = (connCount[e.target] || 0) + 1;
    }

    // Criar nós com posição circular + jitter
    const nodes: BrainNode[] = data.nodes.map((n, i) => {
      const angle = (i / data.nodes.length) * Math.PI * 2;
      const spread = Math.min(w, h) * 0.35;
      const jitter = (Math.random() - 0.5) * 40;
      const conns = connCount[n.id] || 0;

      return {
        id: n.id,
        label: n.label || n.id,
        category: n.category || detectCategory(n.id),
        x: cx + Math.cos(angle) * (spread + jitter),
        y: cy + Math.sin(angle) * (spread + jitter),
        vx: 0,
        vy: 0,
        radius: Math.max(4, Math.min(12, 3 + conns * 2)),
        connections: conns,
        pulsePhase: Math.random() * Math.PI * 2,
      };
    });

    // Criar arestas com pulso
    const edges: BrainEdge[] = data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      pulseProgress: Math.random(),
      pulseSpeed: 0.003 + Math.random() * 0.005,
    }));

    nodesRef.current = nodes;
    edgesRef.current = edges;
  }, [data]);

  // Loop de animação
  const animate = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || zenMode) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;

    // Resize canvas se necessário
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.scale(dpr, dpr);
    }

    const nodes = nodesRef.current;
    const edges = edgesRef.current;
    const now = performance.now() / 1000;

    // Limpar
    ctx.clearRect(0, 0, w, h);

    // Fundo sutil com gradiente radial
    const bgGrad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w * 0.6);
    bgGrad.addColorStop(0, "rgba(15,23,42,0.02)");
    bgGrad.addColorStop(1, "rgba(15,23,42,0)");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    // === FÍSICA: forças ===
    for (const node of nodes) {
      // Repulsão entre nós
      for (const other of nodes) {
        if (node.id === other.id) continue;
        const dx = node.x - other.x;
        const dy = node.y - other.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const minDist = 60;
        if (dist < minDist * 3) {
          const force = (minDist * minDist) / (dist * dist) * 0.3;
          node.vx += (dx / dist) * force;
          node.vy += (dy / dist) * force;
        }
      }

      // Atração ao centro
      const cx = w / 2;
      const cy = h / 2;
      node.vx += (cx - node.x) * 0.0003;
      node.vy += (cy - node.y) * 0.0003;

      // Damping
      node.vx *= 0.92;
      node.vy *= 0.92;

      // Aplicar velocidade (respeitando limites do canvas)
      node.x = Math.max(node.radius, Math.min(w - node.radius, node.x + node.vx));
      node.y = Math.max(node.radius, Math.min(h - node.radius, node.y + node.vy));
    }

    // Atração entre nós conectados
    for (const edge of edges) {
      const src = nodeMap.get(edge.source);
      const tgt = nodeMap.get(edge.target);
      if (!src || !tgt) continue;

      const dx = tgt.x - src.x;
      const dy = tgt.y - src.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const idealDist = 100;
      const force = (dist - idealDist) * 0.002;

      src.vx += (dx / dist) * force;
      src.vy += (dy / dist) * force;
      tgt.vx -= (dx / dist) * force;
      tgt.vy -= (dy / dist) * force;
    }

    // === RENDERIZAÇÃO: arestas ===
    const isDark = document.documentElement.classList.contains("dark");

    for (const edge of edges) {
      const src = nodeMap.get(edge.source);
      const tgt = nodeMap.get(edge.target);
      if (!src || !tgt) continue;

      // Se há foco, esmaecer arestas não conectadas
      const isFocusedEdge = focusedNode
        ? edge.source === focusedNode || edge.target === focusedNode
        : true;

      const alpha = isFocusedEdge ? 0.4 : 0.05;

      ctx.beginPath();
      ctx.moveTo(src.x, src.y);
      ctx.lineTo(tgt.x, tgt.y);
      ctx.strokeStyle = isDark
        ? `rgba(100,116,139,${alpha})`
        : `rgba(148,163,184,${alpha})`;
      ctx.lineWidth = isFocusedEdge ? 1.5 : 0.5;
      ctx.stroke();

      // Pulso elétrico na aresta
      edge.pulseProgress = (edge.pulseProgress + edge.pulseSpeed) % 1;
      if (isFocusedEdge) {
        const px = src.x + (tgt.x - src.x) * edge.pulseProgress;
        const py = src.y + (tgt.y - src.y) * edge.pulseProgress;
        const pulseColor = getCategoryColor(src.category);

        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = pulseColor;
        ctx.fill();

        // Glow do pulso
        const pulseGlow = ctx.createRadialGradient(px, py, 0, px, py, 8);
        pulseGlow.addColorStop(0, pulseColor.replace(")", ",0.4)").replace("rgb", "rgba"));
        pulseGlow.addColorStop(1, "transparent");
        ctx.beginPath();
        ctx.arc(px, py, 8, 0, Math.PI * 2);
        ctx.fillStyle = pulseGlow;
        ctx.fill();
      }
    }

    // === RENDERIZAÇÃO: nós ===
    for (const node of nodes) {
      const isFocused = focusedNode
        ? node.id === focusedNode || nodes.some((n) => {
            const connected = edges.some(
              (e) =>
                (e.source === focusedNode && e.target === node.id) ||
                (e.target === focusedNode && e.source === node.id)
            );
            return connected && n.id === node.id;
          })
        : true;

      const isHovered = hoveredNode === node.id;
      const alpha = isFocused ? 1 : 0.15;
      const color = getCategoryColor(node.category);
      const glow = getCategoryGlow(node.category);

      // Pulso orgânico (respiração)
      const pulse = 1 + Math.sin(now * 1.5 + node.pulsePhase) * 0.12;
      const r = node.radius * pulse * (isHovered ? 1.4 : 1);

      // Glow exterior
      if (isFocused) {
        const outerGlow = ctx.createRadialGradient(node.x, node.y, r, node.x, node.y, r * 3);
        outerGlow.addColorStop(0, glow);
        outerGlow.addColorStop(1, "transparent");
        ctx.beginPath();
        ctx.arc(node.x, node.y, r * 3, 0, Math.PI * 2);
        ctx.fillStyle = outerGlow;
        ctx.fill();
      }

      // Núcleo do neurônio
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);

      // Gradiente interno
      const nodeGrad = ctx.createRadialGradient(
        node.x - r * 0.3, node.y - r * 0.3, 0,
        node.x, node.y, r
      );
      nodeGrad.addColorStop(0, color);
      nodeGrad.addColorStop(1, adjustAlpha(color, 0.7 * alpha));
      ctx.fillStyle = nodeGrad;
      ctx.globalAlpha = alpha;
      ctx.fill();
      ctx.globalAlpha = 1;

      // Label (só para nós focados ou hovered)
      if ((isFocused && (node.connections > 0 || isHovered)) || isHovered) {
        ctx.font = `${isHovered ? "bold " : ""}10px ui-monospace, monospace`;
        ctx.textAlign = "center";
        ctx.fillStyle = isDark
          ? `rgba(226,232,240,${alpha})`
          : `rgba(30,41,59,${alpha})`;
        const labelText = node.label.length > 25
          ? node.label.slice(0, 22) + "…"
          : node.label;
        ctx.fillText(labelText, node.x, node.y + r + 14);
      }
    }

    animFrameRef.current = requestAnimationFrame(animate);
  }, [focusedNode, hoveredNode, zenMode]);

  // Iniciar animação
  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [animate]);

  // Handlers de mouse
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    mouseRef.current.x = x;
    mouseRef.current.y = y;

    // Drag
    if (mouseRef.current.down && mouseRef.current.dragNode) {
      const node = nodesRef.current.find((n) => n.id === mouseRef.current.dragNode);
      if (node) {
        node.x = x;
        node.y = y;
        node.vx = 0;
        node.vy = 0;
      }
      return;
    }

    // Hover detect
    const hovered = nodesRef.current.find(
      (n) => Math.sqrt((n.x - x) ** 2 + (n.y - y) ** 2) < n.radius + 6
    );
    setHoveredNode(hovered?.id || null);
    canvas.style.cursor = hovered ? "pointer" : "grab";
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    mouseRef.current.down = true;

    const clicked = nodesRef.current.find(
      (n) => Math.sqrt((n.x - x) ** 2 + (n.y - y) ** 2) < n.radius + 6
    );

    if (clicked) {
      mouseRef.current.dragNode = clicked.id;
      canvas.style.cursor = "grabbing";
    }
  }, []);

  const handleMouseUp = useCallback(() => {
    if (mouseRef.current.dragNode && !mouseRef.current.down) return;
    const wasDragging = mouseRef.current.dragNode;

    mouseRef.current.down = false;
    mouseRef.current.dragNode = null;

    // Se foi clique (não drag), focar no nó
    if (wasDragging) {
      const canvas = canvasRef.current;
      if (canvas) {
        const rect = canvas.getBoundingClientRect();
        const x = mouseRef.current.x;
        const y = mouseRef.current.y;
        const clicked = nodesRef.current.find(
          (n) => Math.sqrt((n.x - x) ** 2 + (n.y - y) ** 2) < n.radius + 6
        );
        if (clicked) {
          setFocusedNode((prev) => (prev === clicked.id ? null : clicked.id));
          onNodeClick?.(clicked.id);
        }
      }
    }
  }, [onNodeClick]);

  // Teclado
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "z" || e.key === "Z") setZenMode((prev) => !prev);
      if (e.key === "0") {
        // Reset posições
        const canvas = canvasRef.current;
        if (!canvas) return;
        const w = canvas.getBoundingClientRect().width;
        const h = canvas.getBoundingClientRect().height;
        nodesRef.current.forEach((n, i) => {
          const angle = (i / nodesRef.current.length) * Math.PI * 2;
          const spread = Math.min(w, h) * 0.35;
          n.x = w / 2 + Math.cos(angle) * spread;
          n.y = h / 2 + Math.sin(angle) * spread;
          n.vx = 0;
          n.vy = 0;
        });
      }
      if (e.key === "Escape") setFocusedNode(null);
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Se não há dados, mostrar placeholder
  if (!data || !data.nodes || data.nodes.length === 0) {
    return (
      <div className={`flex items-center justify-center h-full ${className || ""}`}>
        <div className="text-center">
          <div className="text-4xl mb-3">🧠</div>
          <p className="text-sm text-ink-400">Nenhuma nota no vault para visualizar</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative ${className || ""}`}>
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{ touchAction: "none" }}
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          mouseRef.current.down = false;
          mouseRef.current.dragNode = null;
          setHoveredNode(null);
        }}
      />

      {/* Controles */}
      <div className="absolute top-3 right-3 flex gap-2">
        <button
          onClick={() => setZenMode(!zenMode)}
          className={`px-2 py-1 text-[10px] font-mono rounded border transition-colors ${
            zenMode
              ? "bg-ink-900 text-white border-ink-700"
              : "bg-white/80 dark:bg-ink-800/80 text-ink-600 dark:text-ink-400 border-ink-200 dark:border-ink-700"
          }`}
        >
          {zenMode ? "▶ resumir" : "⏸ zen"}
        </button>
        {focusedNode && (
          <button
            onClick={() => setFocusedNode(null)}
            className="px-2 py-1 text-[10px] font-mono rounded border bg-white/80 dark:bg-ink-800/80 text-ink-600 dark:text-ink-400 border-ink-200 dark:border-ink-700"
          >
            ✕ limpar foco
          </button>
        )}
      </div>

      {/* Info do nó focado */}
      {focusedNode && (
        <div className="absolute bottom-3 left-3 px-3 py-2 bg-white/90 dark:bg-ink-800/90 rounded-lg border border-ink-200 dark:border-ink-700 shadow-sm max-w-xs">
          <div className="text-xs font-semibold text-ink-800 dark:text-ink-200 truncate">
            {nodesRef.current.find((n) => n.id === focusedNode)?.label}
          </div>
          <div className="text-[10px] font-mono text-ink-400 mt-0.5">
            {nodesRef.current.find((n) => n.id === focusedNode)?.connections || 0} conexões
          </div>
        </div>
      )}

      {/* Legenda */}
      <div className="absolute bottom-3 right-3 flex flex-wrap gap-x-3 gap-y-1 text-[9px] font-mono text-ink-400">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-500" /> projetos
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-500" /> pessoas
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue-500" /> conceitos
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-emerald-500" /> empresas
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-violet-500" /> eventos
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function adjustAlpha(hexColor: string, alpha: number): string {
  // Converte hex ou rgb pra rgba com alpha
  if (hexColor.startsWith("rgba")) return hexColor;
  if (hexColor.startsWith("rgb(")) {
    return hexColor.replace("rgb(", "rgba(").replace(")", `,${alpha})`);
  }
  if (hexColor.startsWith("#")) {
    const r = parseInt(hexColor.slice(1, 3), 16);
    const g = parseInt(hexColor.slice(3, 5), 16);
    const b = parseInt(hexColor.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }
  return hexColor;
}
