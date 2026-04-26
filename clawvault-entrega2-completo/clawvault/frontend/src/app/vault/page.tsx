"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import {
  Brain,
  MagnifyingGlass,
  X,
  Trash,
  ArrowLeft,
  FolderOpen,
  CaretDown,
  CaretRight,
  Vault as VaultIcon,
  File,
  BookOpen,
  Lightbulb,
  CalendarBlank,
  User,
  SquaresFour,
  Stack,
  Sparkle,
} from "@phosphor-icons/react/dist/ssr";

// ─── Types ───────────────────────────────────────────────────────

interface VaultLayer {
  key: string;
  label: string;
  count: number;
  path: string;
  children?: { key: string; label: string; count: number; path: string }[];
}

interface NoteItem {
  path: string;
  title: string;
  snippet: string;
  layer: string;
  tags: string[];
}

type ViewMode = "browse" | "brain";

// ─── Phosphor Icon Components (SSR-safe wrappers) ────────────────

function IconSearch({ size = 18 }: { size?: number }) { return <MagnifyingGlass size={size} />; }
function IconX({ size = 14 }: { size?: number }) { return <X size={size} />; }
function IconTrash({ size = 14 }: { size?: number }) { return <Trash size={size} />; }
function IconArrowLeft({ size = 16 }: { size?: number }) { return <ArrowLeft size={size} />; }
function IconBrain({ size = 16 }: { size?: number }) { return <Brain size={size} />; }
function IconFolder({ size = 14 }: { size?: number }) { return <FolderOpen size={size} />; }
function IconChevronDown() { return <CaretDown size={12} />; }
function IconChevronRight() { return <CaretRight size={12} />; }
function IconVault({ size = 18 }: { size?: number }) { return <VaultIcon size={size} />; }
function IconFile({ size = 14 }: { size?: number }) { return <File size={size} />; }
function IconLayers({ size = 28 }: { size?: number }) { return <Stack size={size} />; }
function IconProjects({ size = 14 }: { size?: number }) { return <BookOpen size={size} />; }
function IconConcepts({ size = 14 }: { size?: number }) { return <Lightbulb size={size} />; }
function IconEvents({ size = 14 }: { size?: number }) { return <CalendarBlank size={size} />; }
function IconPeople({ size = 14 }: { size?: number }) { return <User size={size} />; }
function IconGrid({ size = 14 }: { size?: number }) { return <SquaresFour size={size} />; }

// ─── Colors ──────────────────────────────────────────────────────

const CAT_COLORS: Record<string, string> = {
  projetos: "#d4a574",
  conceitos: "#5a7ea4",
  eventos: "#6b8e5a",
  pessoas: "#b54a3c",
  empresas: "#c99e45",
  drafts: "#9b7cb8",
  index: "#82807a",
  other: "#82807a",
};

function catColor(cat: string): string {
  return CAT_COLORS[cat] || CAT_COLORS.other;
}

function hexToRgba(hex: string, a: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
}

function darkenHex(hex: string, amt: number): string {
  const r = Math.max(0, parseInt(hex.slice(1, 3), 16) - amt);
  const g = Math.max(0, parseInt(hex.slice(3, 5), 16) - amt);
  const b = Math.max(0, parseInt(hex.slice(5, 7), 16) - amt);
  return `rgb(${r},${g},${b})`;
}

function fmtDate(path: string): string {
  const m = path.match(/(\d{4}-\d{2}-\d{2})/);
  if (!m) return "";
  const [, y, mo, d] = m[1].split(/-/);
  return `${d}/${mo}/${y}`;
}

function catIcon(cat: string, size = 14) {
  switch (cat) {
    case "projetos": return <IconProjects size={size} />;
    case "conceitos": return <IconConcepts size={size} />;
    case "eventos": return <IconEvents size={size} />;
    case "pessoas": return <IconPeople size={size} />;
    default: return <IconFile size={size} />;
  }
}

// ─── Main Page ───────────────────────────────────────────────────

export default function VaultPage() {
  const [layers, setLayers] = useState<VaultLayer[]>([]);
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [filteredNotes, setFilteredNotes] = useState<NoteItem[]>([]);
  const [selectedNote, setSelectedNote] = useState<NoteItem | null>(null);
  const [noteContent, setNoteContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("browse");
  const [expandedLayers, setExpandedLayers] = useState<Set<string>>(new Set(["10_wiki"]));
  const [activeLayer, setActiveLayer] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<{ nodes: any[]; edges: any[] } | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  useEffect(() => {
    api.vaultStatus().then((data) => {
      const parsed: VaultLayer[] = [
        {
          key: "10_wiki", label: "Base de Conhecimento",
          count: data.wiki?.count || 0, path: "10_wiki",
          children: [
            { key: "wiki_projects", label: "Projetos", count: data.wiki_projects?.count || 0, path: "10_wiki/projetos" },
            { key: "wiki_concepts", label: "Conceitos", count: data.wiki_concepts?.count || 0, path: "10_wiki/conceitos" },
            { key: "wiki_events", label: "Eventos", count: data.wiki_events?.count || 0, path: "10_wiki/eventos" },
            { key: "wiki_people", label: "Pessoas", count: data.wiki_people?.count || 0, path: "10_wiki/pessoas" },
          ],
        },
        { key: "00_raw", label: "Dados brutos", count: data.raw?.count || 0, path: "00_raw" },
        { key: "20_output", label: "Outputs", count: data.output?.count || 0, path: "20_output" },
        { key: "30_agents", label: "Agentes", count: data.agents?.count || 0, path: "30_agents" },
        { key: "99_index", label: "Índices", count: data.index?.count || 0, path: "99_index" },
      ].filter((l) => l.count > 0 || l.children);
      setLayers(parsed);
    });
    loadAllNotes();
  }, []);

  async function loadAllNotes() {
    setLoading(true);
    try {
      const data = await api.vaultSearch("*", 500);
      const results: NoteItem[] = (data.results || []).map((r: any) => ({
        path: r.path,
        title: r.path.split("/").pop()?.replace(".md", "") || r.path,
        snippet: r.snippet || "",
        layer: r.layer || r.path.split("/")[1] || "",
        tags: [],
      }));
      setNotes(results);
      setFilteredNotes(results);
    } catch { setNotes([]); setFilteredNotes([]); }
    finally { setLoading(false); }
  }

  async function search(q: string) {
    setSearchQuery(q);
    if (!q.trim()) {
      setFilteredNotes(activeLayer ? notes.filter((n) => n.path.includes(activeLayer)) : notes);
      return;
    }
    try {
      const data = await api.vaultSearch(q, 200);
      setFilteredNotes((data.results || []).map((r: any) => ({
        path: r.path, title: r.path.split("/").pop()?.replace(".md", "") || r.path,
        snippet: r.snippet || "", layer: r.layer || r.path.split("/")[1] || "", tags: [],
      })));
    } catch { setFilteredNotes([]); }
  }

  async function openNote(note: NoteItem) {
    setSelectedNote(note);
    setDeleteConfirm(null);
    try {
      const data = await api.vaultReadNote(note.path);
      let c = data.content || "";
      if (c.startsWith("---")) { const e = c.indexOf("---", 3); if (e > 0) c = c.slice(e + 3).trim(); }
      setNoteContent(c);
    } catch { setNoteContent(note.snippet || "Erro ao carregar"); }
  }

  async function deleteNote(path: string) {
    try {
      await api.vaultDeleteNote(path);
      const updated = notes.filter((n) => n.path !== path);
      setNotes(updated);
      setFilteredNotes(activeLayer ? updated.filter((n) => n.path.includes(activeLayer)) : updated);
      if (selectedNote?.path === path) { setSelectedNote(null); setNoteContent(""); }
      setDeleteConfirm(null);
    } catch (e) { console.error("Delete failed:", e); }
  }

  function filterByLayer(path: string) {
    if (activeLayer === path) { setActiveLayer(null); setFilteredNotes(notes); }
    else { setActiveLayer(path); setFilteredNotes(notes.filter((n) => n.path.includes(path))); }
    setSearchQuery("");
  }

  function toggleLayer(key: string) {
    const next = new Set(expandedLayers);
    next.has(key) ? next.delete(key) : next.add(key);
    setExpandedLayers(next);
  }

  async function loadGraph() {
    try { const data = await api.vaultGraph(); setGraphData(data); setViewMode("brain"); }
    catch { setGraphData(null); }
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col animate-fade-in">
      {/* Header */}
      <div className="px-5 py-3 border-b border-ink-100 dark:border-ink-800 flex items-center justify-between shrink-0 bg-white dark:bg-ink-950">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent-50 dark:bg-accent-900/20 flex items-center justify-center text-accent-500">
            <IconVault size={17} />
          </div>
          <div>
            <h1 className="font-display text-sm font-bold text-ink-900 dark:text-ink-50">Vault</h1>
            <p className="text-[10px] text-ink-400 font-mono">{notes.length} notas</p>
          </div>
        </div>
        {viewMode === "browse" && (
          <button onClick={loadGraph}
            className="px-3 py-1.5 text-[11px] font-medium rounded-lg bg-accent-50 dark:bg-accent-900/20 text-accent-600 dark:text-accent-300 hover:bg-accent-100 dark:hover:bg-accent-900/30 transition-colors flex items-center gap-1.5">
            <IconBrain size={13} /> Cérebro
          </button>
        )}
      </div>

      {/* Content */}
      {viewMode === "brain" && graphData ? (
        <BrainView data={graphData} notes={notes}
          onOpenNote={(n) => { setViewMode("browse"); openNote(n); }}
          onBack={() => setViewMode("browse")} />
      ) : (
        <div className="flex-1 flex min-h-0">
          {/* Sidebar */}
          <div className="w-44 border-r border-ink-100 dark:border-ink-800 flex flex-col shrink-0 bg-white/30 dark:bg-ink-950/50">
            <div className="p-3">
              <div className="relative">
                <span className="absolute left-2.5 top-2 text-ink-400"><IconSearch size={13} /></span>
                <input type="text" value={searchQuery} onChange={(e) => search(e.target.value)}
                  placeholder="Buscar no vault..."
                  className="w-full pl-7 pr-7 py-1.5 text-[11px] border border-ink-200 dark:border-ink-700 rounded-lg bg-white dark:bg-ink-800 text-ink-900 dark:text-ink-100 focus:outline-none focus:ring-2 focus:ring-accent-300/40 placeholder:text-ink-400" />
                {searchQuery && (
                  <button onClick={() => { setSearchQuery(""); setFilteredNotes(activeLayer ? notes.filter((n) => n.path.includes(activeLayer)) : notes); }}
                    className="absolute right-2 top-1.5 text-ink-400 hover:text-ink-600"><IconX size={10} /></button>
                )}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-3">
              <button onClick={() => { setActiveLayer(null); setSearchQuery(""); setFilteredNotes(notes); }}
                className={`w-full text-left px-3 py-2 rounded-lg text-[11px] font-medium transition-colors mb-0.5 flex items-center gap-2 ${
                  !activeLayer ? "bg-accent-50 dark:bg-accent-900/20 text-accent-600 dark:text-accent-300" : "text-ink-500 hover:bg-ink-50 dark:hover:bg-ink-800"}`}>
                <IconGrid size={13} /> Todas ({notes.length})
              </button>
              {layers.map((layer) => layer.count > 0 && (
                <div key={layer.key}>
                  <button onClick={() => { if (layer.children) toggleLayer(layer.key); else filterByLayer(layer.path); }}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] transition-colors ${
                      activeLayer === layer.path ? "bg-accent-50 dark:bg-accent-900/20 text-accent-600 dark:text-accent-300" : "text-ink-600 dark:text-ink-400 hover:bg-ink-50 dark:hover:bg-ink-800"}`}>
                    {layer.children ? (expandedLayers.has(layer.key) ? <IconChevronDown /> : <IconChevronRight />) : <span className="w-3" />}
                    <IconFolder size={13} />
                    <span className="flex-1 truncate">{layer.label}</span>
                    <span className="font-mono text-[10px] text-ink-400">{layer.count}</span>
                  </button>
                  {expandedLayers.has(layer.key) && layer.children && (
                    <div className="ml-5">
                      {layer.children.filter((c) => c.count > 0).map((child) => (
                        <button key={child.key} onClick={() => filterByLayer(child.path)}
                          className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[11px] transition-colors ${
                            activeLayer === child.path ? "bg-accent-50 dark:bg-accent-900/20 text-accent-600 dark:text-accent-300" : "text-ink-500 hover:bg-ink-50 dark:hover:bg-ink-800"}`}>
                          {catIcon(child.key.split("_")[1])}
                          <span className="flex-1 truncate">{child.label}</span>
                          <span className="font-mono text-[10px] text-ink-400">{child.count}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Note list */}
          <div className="w-64 border-r border-ink-100 dark:border-ink-800 flex flex-col shrink-0">
            <div className="px-4 py-2.5 border-b border-ink-100 dark:border-ink-800 shrink-0">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-400">
                {searchQuery ? `Resultados (${filteredNotes.length})` : activeLayer ? `Filtrado (${filteredNotes.length})` : `Notas (${filteredNotes.length})`}
              </p>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="flex items-center justify-center py-12"><div className="w-4 h-4 border-2 border-ink-200 border-t-accent-400 rounded-full animate-spin" /></div>
              ) : filteredNotes.length === 0 ? (
                <div className="px-4 py-12 text-center text-[11px] text-ink-400">Nenhuma nota</div>
              ) : filteredNotes.map((note, i) => (
                <button key={i} onClick={() => openNote(note)}
                  className={`w-full text-left px-4 py-2.5 border-b border-ink-50 dark:border-ink-800/50 transition-colors group ${
                    selectedNote?.path === note.path ? "bg-accent-50 dark:bg-accent-900/15 border-l-2 border-l-accent-400" : "hover:bg-ink-50 dark:hover:bg-ink-800/50 border-l-2 border-l-transparent"}`}>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: catColor(note.path.split("/")[1] || "other") }} />
                    <span className="text-[12px] font-medium text-ink-800 dark:text-ink-200 truncate flex-1">
                      {note.title.replace(/^\d{4}-\d{2}-\d{2}[-_]/, "").replace(/-/g, " ")}
                    </span>
                    <button onClick={(e) => { e.stopPropagation(); setDeleteConfirm(note.path); }}
                      className="opacity-0 group-hover:opacity-100 text-ink-300 hover:text-red-500 transition-all p-0.5">
                      <IconTrash size={11} />
                    </button>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 ml-4">
                    <span className="text-[9px] font-mono text-ink-400 truncate">{note.path.split("/")[1] || ""}</span>
                    {fmtDate(note.path) && <span className="text-[9px] text-ink-300 ml-auto">{fmtDate(note.path)}</span>}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Note content */}
          <div className="flex-1 flex flex-col min-w-0">
            {selectedNote ? (
              <>
                <div className="px-5 py-2.5 border-b border-ink-100 dark:border-ink-800 shrink-0">
                  <div className="flex items-center gap-3">
                    <button onClick={() => setSelectedNote(null)} className="text-ink-400 hover:text-ink-600 dark:hover:text-ink-300 shrink-0"><IconArrowLeft size={15} /></button>
                    <div className="min-w-0 flex-1">
                      <h2 className="text-[12px] font-semibold text-ink-900 dark:text-ink-50 truncate">{selectedNote.title.replace(/^\d{4}-\d{2}-\d{2}[-_]/, "").replace(/-/g, " ")}</h2>
                      <p className="text-[9px] font-mono text-ink-400 mt-0.5 truncate">{selectedNote.path}</p>
                    </div>
                  </div>
                  {deleteConfirm === selectedNote.path ? (
                    <div className="flex items-center justify-between mt-2 p-2 rounded-lg bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800/30">
                      <span className="text-[11px] text-red-600 dark:text-red-400">Apagar esta nota?</span>
                      <div className="flex items-center gap-1.5">
                        <button onClick={() => deleteNote(selectedNote.path)} className="px-3 py-1 text-[10px] font-semibold rounded-md bg-red-500 text-white hover:bg-red-600 transition-colors">Apagar</button>
                        <button onClick={() => setDeleteConfirm(null)} className="px-3 py-1 text-[10px] font-medium rounded-md bg-white dark:bg-ink-700 text-ink-600 dark:text-ink-300 border border-ink-200 dark:border-ink-600 hover:bg-ink-50 dark:hover:bg-ink-600 transition-colors">Cancelar</button>
                      </div>
                    </div>
                  ) : (
                    <button onClick={() => setDeleteConfirm(selectedNote.path)} className="mt-1.5 text-[10px] text-ink-400 hover:text-red-500 transition-colors flex items-center gap-1">
                      <IconTrash size={10} /> Excluir nota
                    </button>
                  )}
                </div>
                <div className="flex-1 overflow-y-auto px-5 py-4">
                  <article className="prose prose-sm dark:prose-invert max-w-none text-ink-800 dark:text-ink-200 whitespace-pre-wrap leading-relaxed text-[13px]">
                    {noteContent || "Sem conteúdo"}
                  </article>
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center px-8">
                <div className="w-16 h-16 rounded-2xl bg-ink-50 dark:bg-ink-800 flex items-center justify-center mb-4 text-ink-300 dark:text-ink-600">
                  <IconLayers size={28} />
                </div>
                <h3 className="font-display text-sm font-semibold text-ink-700 dark:text-ink-300 mb-1">Selecione uma nota</h3>
                <p className="text-[11px] text-ink-400 max-w-xs">Navegue pelas categorias ou use a busca.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Brain Visualization ─────────────────────────────────────────

function BrainView({ data, notes, onOpenNote, onBack }: {
  data: { nodes: any[]; edges: any[] };
  notes: NoteItem[];
  onOpenNote: (note: NoteItem) => void;
  onBack: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedBrainNode, setSelectedBrainNode] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const nodesRef = useRef<any[]>([]);
  const neuralEdgesRef = useRef<any[]>([]);
  const edgesRef = useRef<any[]>([]);
  const animRef = useRef<number>(0);
  const initDone = useRef(false);
  const dragRef = useRef<{ down: boolean; node: string | null }>({ down: false, node: null });

  const maybeInit = useCallback(() => {
    if (initDone.current || !data.nodes.length) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    if (rect.width < 50 || rect.height < 50) return;

    const w = rect.width, h = rect.height;
    const cx = w / 2, cy = h / 2;
    const PADDING = 70; // leave room for legend at bottom and header at top

    const cats: Record<string, any[]> = {};
    data.nodes.forEach((n) => { const c = n.category || "other"; if (!cats[c]) cats[c] = []; cats[c].push(n); });
    const catKeys = Object.keys(cats);

    const leftCats = catKeys.slice(0, Math.ceil(catKeys.length / 2));
    const rightCats = catKeys.slice(Math.ceil(catKeys.length / 2));

    const nodes: any[] = [];
    function placeHemisphere(catList: string[], side: "left" | "right") {
      const sign = side === "left" ? -1 : 1;
      const hcx = cx + sign * w * 0.18;
      const hcy = cy;
      catList.forEach((cat, ci) => {
        const catNodes = cats[cat];
        const angle = ((ci / catList.length) - 0.5) * Math.PI * 1.1;
        const radius = Math.min(w, h - PADDING * 2) * 0.12 + ci * 12;
        const clusterCx = hcx + Math.cos(angle) * radius * 0.5;
        const clusterCy = hcy + Math.sin(angle) * radius * 0.7;
        catNodes.forEach((n, ni) => {
          const la = (ni / catNodes.length) * Math.PI * 2;
          const spread = 20 + Math.sqrt(catNodes.length) * 7;
          nodes.push({
            id: n.id, label: n.label || n.id, category: cat,
            x: clusterCx + Math.cos(la) * spread * (0.5 + Math.random() * 0.5),
            y: clusterCy + Math.sin(la) * spread * (0.5 + Math.random() * 0.5),
            vx: 0, vy: 0,
            radius: Math.max(3.5, Math.min(6, 3 + Math.log2(catNodes.length))),
            pulsePhase: Math.random() * Math.PI * 2,
            path: n.path || n.id,
          });
        });
      });
    }
    placeHemisphere(leftCats, "left");
    placeHemisphere(rightCats, "right");

    // Constrain nodes to visible area
    nodes.forEach((n) => {
      n.x = Math.max(40, Math.min(w - 40, n.x));
      n.y = Math.max(PADDING, Math.min(h - PADDING - 30, n.y));
    });

    nodesRef.current = nodes;

    // Neural edges
    const nEdges: any[] = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dist = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
        if (dist < 100 && Math.random() < 0.25) {
          nEdges.push({
            source: nodes[i].id, target: nodes[j].id,
            pulseProgress: Math.random(), pulseSpeed: 0.002 + Math.random() * 0.004,
            brightness: 0.12 + Math.random() * 0.12,
          });
        }
      }
    }
    neuralEdgesRef.current = nEdges;
    edgesRef.current = data.edges.map((e: any) => ({
      source: e.source, target: e.target,
      pulseProgress: Math.random(), pulseSpeed: 0.003 + Math.random() * 0.005, brightness: 0.4,
    }));
    initDone.current = true;
  }, [data]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) { animRef.current = requestAnimationFrame(draw); return; }
    const ctx = canvas.getContext("2d");
    if (!ctx) { animRef.current = requestAnimationFrame(draw); return; }
    maybeInit();

    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const rw = Math.round(rect.width * dpr), rh = Math.round(rect.height * dpr);
    if (canvas.width !== rw || canvas.height !== rh) { canvas.width = rw; canvas.height = rh; }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const w = rect.width, h = rect.height;
    const nodes = nodesRef.current;
    if (!nodes.length) { animRef.current = requestAnimationFrame(draw); return; }
    const t = performance.now() / 1000;
    const isDark = document.documentElement.classList.contains("dark");
    const BOTTOM_PAD = 55;

    // BG
    ctx.fillStyle = isDark ? "#0a0a09" : "#f5f3ef";
    ctx.fillRect(0, 0, w, h);

    // Hemispheric glows
    [w * 0.32, w * 0.68].forEach((gx) => {
      const g = ctx.createRadialGradient(gx, h * 0.48, 0, gx, h * 0.48, w * 0.22);
      g.addColorStop(0, isDark ? "rgba(212,165,116,0.025)" : "rgba(212,165,116,0.035)");
      g.addColorStop(1, "transparent");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    });

    // Fissure
    ctx.beginPath();
    ctx.moveTo(w / 2, h * 0.12);
    ctx.bezierCurveTo(w / 2 - 3, h * 0.3, w / 2 + 3, h * 0.6, w / 2, h * 0.82);
    ctx.strokeStyle = isDark ? "rgba(42,42,40,0.6)" : "rgba(228,227,224,0.6)";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Physics
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    for (const n of nodes) {
      n.vx += (w / 2 - n.x) * 0.0001;
      n.vy += ((h - BOTTOM_PAD) / 2 - n.y) * 0.0001;
      for (const o of nodes) {
        if (n.id === o.id) continue;
        const d = Math.hypot(n.x - o.x, n.y - o.y) || 1;
        if (d < 90) { const f = 500 / (d * d); n.vx += ((n.x - o.x) / d) * f * 0.25; n.vy += ((n.y - o.y) / d) * f * 0.25; }
      }
      n.vx *= 0.88; n.vy *= 0.88;
      n.x = Math.max(30, Math.min(w - 30, n.x + n.vx));
      n.y = Math.max(40, Math.min(h - BOTTOM_PAD - 20, n.y + n.vy));
    }

    const isVisible = (n: any) => !activeCategory || n.category === activeCategory;

    // Neural edges
    for (const e of neuralEdgesRef.current) {
      const s = nodeMap.get(e.source), tg = nodeMap.get(e.target);
      if (!s || !tg) continue;
      const sv = isVisible(s), tv = isVisible(tg);
      const active = !hoveredNode || s.id === hoveredNode || tg.id === hoveredNode;
      const cm = !activeCategory || (sv && tv);
      const a = cm ? (active ? e.brightness : e.brightness * 0.2) : 0.015;
      ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(tg.x, tg.y);
      ctx.strokeStyle = isDark ? `rgba(180,170,150,${a})` : `rgba(140,135,125,${a})`;
      ctx.lineWidth = cm && active ? 0.7 : 0.25;
      ctx.stroke();
      if (cm && active && e.brightness > 0.18) {
        e.pulseProgress = (e.pulseProgress + e.pulseSpeed) % 1;
        const px = s.x + (tg.x - s.x) * e.pulseProgress;
        const py = s.y + (tg.y - s.y) * e.pulseProgress;
        const pa = 0.35 + 0.25 * Math.sin(e.pulseProgress * Math.PI);
        ctx.beginPath(); ctx.arc(px, py, 1.2, 0, Math.PI * 2);
        ctx.fillStyle = isDark ? `rgba(212,165,116,${pa})` : `rgba(166,114,56,${pa})`;
        ctx.fill();
      }
    }

    // Real edges
    for (const e of edgesRef.current) {
      const s = nodeMap.get(e.source), tg = nodeMap.get(e.target);
      if (!s || !tg) continue;
      if (!isVisible(s) || !isVisible(tg)) continue;
      ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(tg.x, tg.y);
      ctx.strokeStyle = isDark ? "rgba(212,165,116,0.3)" : "rgba(166,114,56,0.3)";
      ctx.lineWidth = 1; ctx.stroke();
      e.pulseProgress = (e.pulseProgress + e.pulseSpeed) % 1;
      const px = s.x + (tg.x - s.x) * e.pulseProgress;
      const py = s.y + (tg.y - s.y) * e.pulseProgress;
      ctx.beginPath(); ctx.arc(px, py, 2, 0, Math.PI * 2);
      ctx.fillStyle = "#d4a574"; ctx.fill();
    }

    // Nodes
    for (const n of nodes) {
      const vis = isVisible(n);
      const isConn = !hoveredNode || n.id === hoveredNode || neuralEdgesRef.current.some((e) =>
        (e.source === hoveredNode && e.target === n.id) || (e.target === hoveredNode && e.source === n.id));
      const isSel = selectedBrainNode === n.id;
      const a = vis ? (isConn ? 1 : 0.15) : 0.03;
      const color = catColor(n.category);
      const pulse = 1 + 0.04 * Math.sin(1.5 * t + n.pulsePhase);
      const r = n.radius * pulse * (isSel ? 1.3 : 1);

      if (vis && a > 0.5) {
        const glow = ctx.createRadialGradient(n.x, n.y, r * 0.5, n.x, n.y, r * 2.5);
        glow.addColorStop(0, hexToRgba(color, 0.18 * a));
        glow.addColorStop(1, hexToRgba(color, 0));
        ctx.beginPath(); ctx.arc(n.x, n.y, r * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = glow; ctx.fill();
      }
      ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.globalAlpha = a;
      const grad = ctx.createRadialGradient(n.x - r * 0.2, n.y - r * 0.2, 0, n.x, n.y, r);
      grad.addColorStop(0, color); grad.addColorStop(1, darkenHex(color, 40));
      ctx.fillStyle = grad; ctx.fill();
      if (isSel) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5; ctx.stroke(); }
      ctx.globalAlpha = 1;

      if (vis && a > 0.3) {
        const label = n.label.length > 28 ? n.label.slice(0, 25) + "…" : n.label;
        ctx.font = `${isSel ? "600" : "500"} 12px Manrope, system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.fillStyle = isDark ? `rgba(240,240,238,${a * 0.9})` : `rgba(26,26,25,${a * 0.9})`;
        ctx.fillText(label, n.x, n.y + r + 15);
      }
    }

    animRef.current = requestAnimationFrame(draw);
  }, [hoveredNode, selectedBrainNode, activeCategory, maybeInit]);

  useEffect(() => {
    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  }, [draw]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current; if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    if (dragRef.current.down && dragRef.current.node) {
      const node = nodesRef.current.find((n) => n.id === dragRef.current.node);
      if (node) { node.x = x; node.y = y; node.vx = 0; node.vy = 0; }
      return;
    }
    const found = nodesRef.current.find((n) => Math.hypot(n.x - x, n.y - y) < n.radius + 10);
    setHoveredNode(found?.id || null);
    canvas.style.cursor = found ? "pointer" : "default";
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current; if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    const found = nodesRef.current.find((n) => Math.hypot(n.x - x, n.y - y) < n.radius + 10);
    if (found) { dragRef.current = { down: true, node: found.id }; canvas.style.cursor = "grabbing"; }
  }, []);

  const handleMouseUp = useCallback(() => {
    const nid = dragRef.current.node;
    dragRef.current = { down: false, node: null };
    if (nid) setSelectedBrainNode((p) => p === nid ? null : nid);
  }, []);

  const handleDoubleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current; if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    const found = nodesRef.current.find((n) => Math.hypot(n.x - x, n.y - y) < n.radius + 10);
    if (found) {
      const note = notes.find((n) => n.path === found.path || n.path.endsWith(`/${found.id}.md`));
      if (note) onOpenNote(note);
    }
  }, [notes, onOpenNote]);

  const categories = [...new Set(nodesRef.current.map((n) => n.category))];
  const catCounts: Record<string, number> = {};
  nodesRef.current.forEach((n) => { catCounts[n.category] = (catCounts[n.category] || 0) + 1; });
  const selectedNode = selectedBrainNode ? nodesRef.current.find((n) => n.id === selectedBrainNode) : null;

  return (
    <div ref={containerRef} className="flex-1 relative" style={{ minHeight: 400 }}>
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" style={{ touchAction: "none" }}
        onMouseMove={handleMouseMove} onMouseDown={handleMouseDown} onMouseUp={handleMouseUp}
        onMouseLeave={() => { dragRef.current = { down: false, node: null }; setHoveredNode(null); }}
        onDoubleClick={handleDoubleClick} />

      {/* Back */}
      <button onClick={onBack}
        className="absolute top-4 left-4 px-3 py-1.5 text-[11px] font-medium rounded-lg bg-white/90 dark:bg-ink-800/90 backdrop-blur-sm border border-ink-200/60 dark:border-ink-700/60 text-ink-600 dark:text-ink-300 hover:bg-white dark:hover:bg-ink-800 transition-colors flex items-center gap-1.5 shadow-sm">
        <IconArrowLeft size={13} /> Voltar
      </button>

      <div className="absolute top-4 left-24 text-[10px] font-mono text-ink-400">
        {data.nodes.length} nós
      </div>
      <div className="absolute top-4 right-4 text-[10px] text-ink-400">
        Clique p/ focar · Duplo clique p/ abrir
      </div>

      {/* Category filter — left sidebar */}
      <div className="absolute top-14 left-4 flex flex-col gap-1">
        <button onClick={() => setActiveCategory(null)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-medium transition-all ${
            !activeCategory ? "bg-white/90 dark:bg-ink-800/90 backdrop-blur-sm text-accent-600 dark:text-accent-300 shadow-sm border border-accent-300/30" : "bg-white/60 dark:bg-ink-800/60 backdrop-blur-sm text-ink-400 hover:text-ink-600 border border-transparent"}`}>
          Tudo
        </button>
        {categories.map((cat) => (
          <button key={cat} onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-medium transition-all border ${
              activeCategory === cat ? "backdrop-blur-sm shadow-sm" : "bg-white/60 dark:bg-ink-800/60 backdrop-blur-sm text-ink-400 hover:text-ink-600 border-transparent"
            }`}
            style={activeCategory === cat ? { backgroundColor: hexToRgba(catColor(cat), 0.15), borderColor: hexToRgba(catColor(cat), 0.3), color: catColor(cat), boxShadow: `0 1px 3px ${hexToRgba(catColor(cat), 0.15)}` } : {}}>
            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: catColor(cat) }} />
            {cat}
          </button>
        ))}
      </div>

      {/* Selected node */}
      {selectedNode && (
        <div className="absolute bottom-4 right-4 w-60 bg-white/95 dark:bg-ink-800/95 backdrop-blur-sm rounded-xl border border-ink-100 dark:border-ink-700 shadow-lg p-3">
          <div className="flex items-center justify-between mb-1.5">
            <h3 className="text-[12px] font-semibold text-ink-900 dark:text-ink-50 truncate pr-2">{selectedNode.label}</h3>
            <button onClick={() => setSelectedBrainNode(null)} className="text-ink-400 hover:text-ink-600 shrink-0"><IconX size={12} /></button>
          </div>
          <div className="flex items-center gap-1.5 mb-2">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: catColor(selectedNode.category) }} />
            <span className="text-[9px] font-mono text-ink-400">{selectedNode.path}</span>
          </div>
          <button onClick={() => {
            const note = notes.find((n) => n.path === selectedNode.path || n.path.endsWith(`/${selectedNode.id}.md`));
            if (note) onOpenNote(note);
          }} className="w-full px-3 py-1.5 text-[11px] font-medium rounded-lg bg-accent-50 dark:bg-accent-900/20 text-accent-600 dark:text-accent-300 hover:bg-accent-100 dark:hover:bg-accent-900/30 transition-colors">
            Abrir nota
          </button>
        </div>
      )}
    </div>
  );
}
