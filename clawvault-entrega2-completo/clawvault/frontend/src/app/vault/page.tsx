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
  List,
} from "@phosphor-icons/react/dist/ssr";

// ─── Types ───────────────────────────────────────────────────────

interface VaultLayer {
  key: string;
  label: string;
  icon?: string;
  count: number;
  path: string;
  children?: { key: string; label: string; icon?: string; count: number; path: string }[];
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
function IconList({ size = 14 }: { size?: number }) { return <List size={size} />; }

// ─── Colors ──────────────────────────────────────────────────────

// Cyber-minimalist palette (Obsidian Purple + Neon Green)
const CV_PURPLE = "#A78BFA";
const CV_GREEN = "#4ADE80";
const CV_DARK = "#111827";

const CV_AMBER = "#FBBF24";
const CV_CYAN = "#22D3EE";
const CV_ROSE = "#FB7185";
const CV_ORANGE = "#FB923C";
const CV_TEAL = "#2DD4BF";

const CAT_COLORS: Record<string, string> = {
  // Vault layer categories — each one a distinct color
  projetos: CV_AMBER,       // Warm amber — projects/active work
  conceitos: CV_CYAN,       // Cyan — concepts/knowledge
  eventos: CV_GREEN,        // Neon green — events/timeline
  pessoas: CV_ROSE,         // Rose — people
  empresas: CV_ORANGE,      // Orange — companies
  drafts: CV_PURPLE,        // Purple — drafts/work in progress
  fatos: CV_TEAL,           // Teal — facts
  index: "#94A3B8",         // Slate — index
  "99_index": "#94A3B8",     // Slate — index
  other: "#6B7280",         // Gray — uncategorized
  // Aliases
  inbox: CV_GREEN,
  projects: CV_AMBER,
  areas: CV_PURPLE,
  resources: CV_CYAN,
  archive: CV_TEAL,
  atlas: "#94A3B8",
  scripts: CV_ORANGE,
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

// Custom cyber-minimalist SVG icons for vault layers
function CvInbox({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 8l4-4h8l4 4" stroke={CV_GREEN} strokeWidth="1.5" />
      <path d="M2 8v10a2 2 0 002 2h16a2 2 0 002-2V8" stroke={CV_PURPLE} strokeWidth="1.5" />
      <path d="M12 8v8M8 12l4 4 4-4" stroke={CV_GREEN} strokeWidth="1.5" />
    </svg>
  );
}
function CvProjects({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" stroke={CV_PURPLE} strokeWidth="1.5" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" stroke={CV_PURPLE} strokeWidth="1.5" />
      <path d="M13 2l1 2" stroke={CV_GREEN} strokeWidth="2" />
    </svg>
  );
}
function CvAreas({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" stroke={CV_PURPLE} strokeWidth="1.5" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" stroke={CV_PURPLE} strokeWidth="1.5" />
      <line x1="12" y1="22.08" x2="12" y2="12" stroke={CV_PURPLE} strokeWidth="1.5" />
      <circle cx="6" cy="6" r="1.5" fill={CV_GREEN} />
      <circle cx="18" cy="6" r="1.5" fill={CV_GREEN} />
      <circle cx="12" cy="18" r="1.5" fill={CV_GREEN} />
    </svg>
  );
}
function CvResources({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" stroke={CV_PURPLE} strokeWidth="1.5" />
      <path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" stroke={CV_PURPLE} strokeWidth="1.5" />
      <path d="M18 3v2" stroke={CV_GREEN} strokeWidth="2" />
    </svg>
  );
}
function CvArchive({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 8v13H3V8" stroke={CV_PURPLE} strokeWidth="1.5" />
      <path d="M1 3h22v5H1z" stroke={CV_PURPLE} strokeWidth="1.5" />
      <path d="M10 12h4" stroke={CV_PURPLE} strokeWidth="1.5" />
      <rect x="15" y="13" width="5" height="4" rx="1" stroke={CV_GREEN} strokeWidth="1" fill="none" />
      <circle cx="17.5" cy="15" r="0.75" fill={CV_GREEN} />
    </svg>
  );
}
function CvAtlas({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="6" r="2" stroke={CV_GREEN} strokeWidth="1.5" />
      <circle cx="18" cy="6" r="2" stroke={CV_GREEN} strokeWidth="1.5" />
      <circle cx="12" cy="12" r="2" stroke={CV_GREEN} strokeWidth="1.5" />
      <circle cx="6" cy="18" r="2" stroke={CV_GREEN} strokeWidth="1.5" />
      <circle cx="18" cy="18" r="2" stroke={CV_GREEN} strokeWidth="1.5" />
      <line x1="7.5" y1="7" x2="10.5" y2="11" stroke={CV_PURPLE} strokeWidth="1" />
      <line x1="13.5" y1="11" x2="16.5" y2="7" stroke={CV_PURPLE} strokeWidth="1" />
      <line x1="7.5" y1="17" x2="10.5" y2="13" stroke={CV_PURPLE} strokeWidth="1" />
      <line x1="13.5" y1="13" x2="16.5" y2="17" stroke={CV_PURPLE} strokeWidth="1" />
    </svg>
  );
}
function CvScripts({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 17 10 11 4 5" stroke={CV_GREEN} strokeWidth="1.5" />
      <line x1="12" y1="19" x2="20" y2="19" stroke={CV_GREEN} strokeWidth="1.5" />
      <circle cx="18" cy="6" r="1" fill={CV_PURPLE} />
      <circle cx="20" cy="9" r="0.8" fill={CV_PURPLE} />
      <circle cx="16" cy="4" r="0.6" fill={CV_PURPLE} />
    </svg>
  );
}

function catIcon(cat: string, size = 14) {
  switch (cat) {
    case "inbox": return <CvInbox size={size} />;
    case "projects": case "projetos": return <CvProjects size={size} />;
    case "areas": return <CvAreas size={size} />;
    case "resources": case "conceitos": return <CvResources size={size} />;
    case "archive": case "eventos": return <CvArchive size={size} />;
    case "atlas": case "index": return <CvAtlas size={size} />;
    case "scripts": return <CvScripts size={size} />;
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
  // Mobile: which panel is visible — "list" | "detail"
  const [mobilePanel, setMobilePanel] = useState<"list" | "detail">("list");

  useEffect(() => {
    api.vaultStatus().then((data) => {
      const parsed: VaultLayer[] = [
        {
          key: "00_inbox", label: "Inbox — Entrada", icon: "inbox",
          count: data.raw?.count || 0, path: "00_raw",
        },
        {
          key: "10_wiki", label: "Base de Conhecimento", icon: "resources",
          count: data.wiki?.count || 0, path: "10_wiki",
          children: [
            { key: "wiki_projects", label: "Projetos", icon: "projects", count: data.wiki_projects?.count || 0, path: "10_wiki/projetos" },
            { key: "wiki_concepts", label: "Conceitos", icon: "resources", count: data.wiki_concepts?.count || 0, path: "10_wiki/conceitos" },
            { key: "wiki_events", label: "Eventos", icon: "archive", count: data.wiki_events?.count || 0, path: "10_wiki/eventos" },
            { key: "wiki_people", label: "Pessoas", icon: "areas", count: data.wiki_people?.count || 0, path: "10_wiki/pessoas" },
          ],
        },
        { key: "20_output", label: "Outputs — Produção", icon: "areas", count: data.output?.count || 0, path: "20_output" },
        { key: "30_agents", label: "Scripts & Agentes", icon: "scripts", count: data.agents?.count || 0, path: "30_agents" },
        { key: "99_index", label: "Atlas — Mapa Mental", icon: "atlas", count: data.index?.count || 0, path: "99_index" },
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
    setMobilePanel("detail");
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
      if (selectedNote?.path === path) { setSelectedNote(null); setNoteContent(""); setMobilePanel("list"); }
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

  function noteTitle(note: NoteItem) {
    return note.title.replace(/^\d{4}-\d{2}-\d{2}[-_]/, "").replace(/-/g, " ");
  }

  return (
    <div className="h-[calc(100vh-4rem)] lg:h-[calc(100vh-4rem)] flex flex-col animate-fade-in">
      {/* Header */}
      <div className="px-4 lg:px-5 py-3 border-b border-[#1E1B2E] flex items-center justify-between shrink-0 bg-[#111827]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#A78BFA]/10 flex items-center justify-center text-[#A78BFA]">
            <IconVault size={17} />
          </div>
          <div>
            <h1 className="font-display text-sm font-bold text-white">Vault</h1>
            <p className="text-[10px] text-[#4ADE80]/60 font-mono">{notes.length} notas</p>
          </div>
        </div>
        {viewMode === "browse" && (
          <button onClick={loadGraph}
            className="px-3 py-1.5 text-[11px] font-medium rounded-lg bg-[#4ADE80]/10 text-[#4ADE80] hover:bg-[#4ADE80]/20 transition-colors flex items-center gap-1.5">
            <IconBrain size={13} /> <span className="hidden sm:inline">Cérebro</span>
          </button>
        )}
      </div>

      {/* Content */}
      {viewMode === "brain" && graphData ? (
        <BrainView data={graphData} notes={notes}
          onOpenNote={(n) => { setViewMode("browse"); openNote(n); }}
          onBack={() => setViewMode("browse")} />
      ) : (
        <div className="flex-1 flex min-h-0 overflow-hidden">
          {/* ==================== MOBILE: single-panel view ==================== */}
          {/* Note detail (mobile) */}
          {mobilePanel === "detail" && selectedNote && (
            <div className="flex-1 flex flex-col min-w-0 md:hidden">
              <div className="px-4 py-2.5 border-b border-[#1E1B2E] shrink-0 bg-[#111827]">
                <div className="flex items-center gap-3">
                  <button onClick={() => { setMobilePanel("list"); }} className="text-[#A78BFA] hover:text-white shrink-0"><IconArrowLeft size={18} /></button>
                  <div className="min-w-0 flex-1">
                    <h2 className="text-[13px] font-semibold text-white truncate">{noteTitle(selectedNote)}</h2>
                    <p className="text-[9px] font-mono text-[#A78BFA]/60 mt-0.5 truncate">{selectedNote.path}</p>
                  </div>
                </div>
                {deleteConfirm === selectedNote.path ? (
                  <div className="flex items-center justify-between mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                    <span className="text-[11px] text-red-400">Apagar esta nota?</span>
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => deleteNote(selectedNote.path)} className="px-3 py-1 text-[10px] font-semibold rounded-md bg-red-500 text-white hover:bg-red-600">Apagar</button>
                      <button onClick={() => setDeleteConfirm(null)} className="px-3 py-1 text-[10px] font-medium rounded-md bg-white/10 text-white/60 border border-white/10">Cancelar</button>
                    </div>
                  </div>
                ) : (
                  <button onClick={() => setDeleteConfirm(selectedNote.path)} className="mt-1.5 text-[10px] text-white/30 hover:text-red-400 transition-colors flex items-center gap-1">
                    <IconTrash size={10} /> Excluir nota
                  </button>
                )}
              </div>
              <div className="flex-1 overflow-y-auto px-4 py-4 bg-[#0D0B14]">
                <article className="prose prose-sm prose-invert max-w-none text-white/80 whitespace-pre-wrap leading-relaxed text-[13px]">
                  {noteContent || "Sem conteúdo"}
                </article>
              </div>
            </div>
          )}

          {/* Note list (mobile) */}
          {(mobilePanel === "list" || !selectedNote) && (
            <div className="flex-1 flex flex-col min-h-0 md:hidden">
              {/* Search bar */}
              <div className="p-3 border-b border-[#1E1B2E] shrink-0">
                <div className="relative">
                  <span className="absolute left-2.5 top-2 text-[#A78BFA]"><IconSearch size={13} /></span>
                  <input type="text" value={searchQuery} onChange={(e) => search(e.target.value)}
                    placeholder="Buscar no vault..."
                    className="w-full pl-7 pr-7 py-2 text-[12px] border border-[#A78BFA]/20 rounded-lg bg-[#111827] text-white placeholder:text-[#A78BFA]/40 focus:outline-none focus:ring-2 focus:ring-[#A78BFA]/30" />
                  {searchQuery && (
                    <button onClick={() => { setSearchQuery(""); setFilteredNotes(activeLayer ? notes.filter((n) => n.path.includes(activeLayer)) : notes); }}
                      className="absolute right-2 top-1.5 text-[#A78BFA]/40 hover:text-white"><IconX size={12} /></button>
                  )}
                </div>
                {/* Category chips */}
                <div className="flex gap-1.5 mt-2 overflow-x-auto pb-1 -mx-1 px-1">
                  <button onClick={() => { setActiveLayer(null); setSearchQuery(""); setFilteredNotes(notes); }}
                    className={`shrink-0 px-2.5 py-1 rounded-full text-[10px] font-medium transition-all ${
                      !activeLayer ? "bg-[#A78BFA] text-white shadow-[0_0_8px_rgba(167,139,250,0.3)]" : "bg-[#1E1B2E] text-[#A78BFA]/60 border border-[#A78BFA]/10"}`}>
                    Todas ({notes.length})
                  </button>
                  {layers.map((layer) => layer.count > 0 && (
                    <button key={layer.key} onClick={() => { if (!layer.children) filterByLayer(layer.path); else toggleLayer(layer.key); }}
                      className={`shrink-0 px-2.5 py-1 rounded-full text-[10px] font-medium transition-all flex items-center gap-1 ${
                        activeLayer === layer.path ? "bg-[#4ADE80] text-[#111827]" : "bg-[#1E1B2E] text-white/50 border border-[#A78BFA]/10"}`}>
                      {catIcon(layer.icon || layer.key, 10)}
                      <span className="hidden sm:inline">{layer.label.split(" — ")[0]}</span>
                      <span className="sm:hidden">{layer.label.split(" — ")[0].slice(0, 3)}</span>
                      <span className="font-mono text-[9px] opacity-70">{layer.count}</span>
                    </button>
                  ))}
                </div>
              </div>
              {/* Notes list */}
              <div className="flex-1 overflow-y-auto bg-[#0D0B14]">
                {loading ? (
                  <div className="flex items-center justify-center py-12"><div className="w-4 h-4 border-2 border-[#A78BFA]/20 border-t-[#4ADE80] rounded-full animate-spin" /></div>
                ) : filteredNotes.length === 0 ? (
                  <div className="px-4 py-12 text-center text-[12px] text-[#A78BFA]/40">Nenhuma nota</div>
                ) : filteredNotes.map((note, i) => (
                  <button key={i} onClick={() => openNote(note)}
                    className={`w-full text-left px-4 py-3 border-b border-[#1E1B2E]/50 transition-colors active:bg-[#A78BFA]/5 ${
                      selectedNote?.path === note.path ? "bg-[#A78BFA]/10 border-l-2 border-l-[#4ADE80]" : "border-l-2 border-l-transparent"}`}>
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: catColor(note.path.split("/")[1] || "other") }} />
                      <span className="text-[13px] font-medium text-white/90 truncate flex-1">
                        {noteTitle(note)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-1 ml-4">
                      <span className="text-[10px] font-mono text-[#A78BFA]/40 truncate">{note.path.split("/")[1] || ""}</span>
                      {fmtDate(note.path) && <span className="text-[10px] text-[#4ADE80]/40 ml-auto">{fmtDate(note.path)}</span>}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ==================== DESKTOP: 3-panel view ==================== */}
          <div className="hidden md:flex flex-1 min-h-0">
            {/* Sidebar */}
            <div className="w-44 border-r border-[#1E1B2E] flex flex-col shrink-0 bg-[#111827]/80">
              <div className="p-3">
                <div className="relative">
                  <span className="absolute left-2.5 top-2 text-[#A78BFA]/60"><IconSearch size={13} /></span>
                  <input type="text" value={searchQuery} onChange={(e) => search(e.target.value)}
                    placeholder="Buscar no vault..."
                    className="w-full pl-7 pr-7 py-1.5 text-[11px] border border-[#A78BFA]/15 rounded-lg bg-[#0D0B14] text-white focus:outline-none focus:ring-2 focus:ring-[#A78BFA]/30 placeholder:text-[#A78BFA]/30" />
                  {searchQuery && (
                    <button onClick={() => { setSearchQuery(""); setFilteredNotes(activeLayer ? notes.filter((n) => n.path.includes(activeLayer)) : notes); }}
                      className="absolute right-2 top-1.5 text-[#A78BFA]/40 hover:text-white"><IconX size={10} /></button>
                  )}
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-2 pb-3">
                <button onClick={() => { setActiveLayer(null); setSearchQuery(""); setFilteredNotes(notes); }}
                  className={`w-full text-left px-3 py-2 rounded-lg text-[11px] font-medium transition-all mb-0.5 flex items-center gap-2 ${
                    !activeLayer ? "bg-[#A78BFA]/15 text-[#A78BFA]" : "text-white/40 hover:bg-[#A78BFA]/5"}`}>
                  <IconGrid size={13} /> Todas ({notes.length})
                </button>
                {layers.map((layer) => layer.count > 0 && (
                  <div key={layer.key}>
                    <button onClick={() => { if (layer.children) toggleLayer(layer.key); else filterByLayer(layer.path); }}
                      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] transition-all ${
                        activeLayer === layer.path ? "bg-[#A78BFA]/15 text-[#A78BFA]" : "text-white/50 hover:bg-[#A78BFA]/5"}`}>
                      {layer.children ? (expandedLayers.has(layer.key) ? <IconChevronDown /> : <IconChevronRight />) : <span className="w-3" />}
                      {catIcon(layer.icon || layer.key, 13)}
                      <span className="flex-1 truncate">{layer.label.split(" — ")[0]}</span>
                      <span className="font-mono text-[10px] text-[#4ADE80]/50">{layer.count}</span>
                    </button>
                    {expandedLayers.has(layer.key) && layer.children && (
                      <div className="ml-5">
                        {layer.children.filter((c) => c.count > 0).map((child) => (
                          <button key={child.key} onClick={() => filterByLayer(child.path)}
                            className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[11px] transition-all ${
                              activeLayer === child.path ? "bg-[#4ADE80]/10 text-[#4ADE80]" : "text-white/30 hover:bg-[#A78BFA]/5"}`}>
                                {catIcon(child.icon || child.key.split("_")[1])}
                                <span className="flex-1 truncate">{child.label}</span>
                                <span className="font-mono text-[10px] text-[#4ADE80]/40">{child.count}</span>
                              </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Note list */}
            <div className="w-64 border-r border-[#1E1B2E] flex flex-col shrink-0 bg-[#111827]">
              <div className="px-4 py-2.5 border-b border-[#1E1B2E] shrink-0">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[#A78BFA]/40">
                  {searchQuery ? `Resultados (${filteredNotes.length})` : activeLayer ? `Filtrado (${filteredNotes.length})` : `Notas (${filteredNotes.length})`}
                </p>
              </div>
              <div className="flex-1 overflow-y-auto">
                {loading ? (
                  <div className="flex items-center justify-center py-12"><div className="w-4 h-4 border-2 border-[#A78BFA]/20 border-t-[#4ADE80] rounded-full animate-spin" /></div>
                ) : filteredNotes.length === 0 ? (
                  <div className="px-4 py-12 text-center text-[11px] text-[#A78BFA]/30">Nenhuma nota</div>
                ) : filteredNotes.map((note, i) => (
                  <button key={i} onClick={() => openNote(note)}
                    className={`w-full text-left px-4 py-2.5 border-b border-[#1E1B2E]/30 transition-all group ${
                      selectedNote?.path === note.path ? "bg-[#A78BFA]/10 border-l-2 border-l-[#4ADE80]" : "hover:bg-[#A78BFA]/5 border-l-2 border-l-transparent"}`}>
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: catColor(note.path.split("/")[1] || "other") }} />
                      <span className="text-[12px] font-medium text-white/80 truncate flex-1">
                        {noteTitle(note)}
                      </span>
                      <button onClick={(e) => { e.stopPropagation(); setDeleteConfirm(note.path); }}
                        className="opacity-0 group-hover:opacity-100 text-white/20 hover:text-red-400 transition-all p-0.5">
                        <IconTrash size={11} />
                      </button>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5 ml-4">
                      <span className="text-[9px] font-mono text-[#A78BFA]/30 truncate">{note.path.split("/")[1] || ""}</span>
                      {fmtDate(note.path) && <span className="text-[9px] text-[#4ADE80]/30 ml-auto">{fmtDate(note.path)}</span>}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Note content */}
            <div className="flex-1 flex flex-col min-w-0 bg-[#0D0B14]">
              {selectedNote ? (
                <>
                  <div className="px-5 py-2.5 border-b border-[#1E1B2E] shrink-0">
                    <div className="flex items-center gap-3">
                      <button onClick={() => setSelectedNote(null)} className="text-[#A78BFA]/40 hover:text-[#A78BFA] shrink-0"><IconArrowLeft size={15} /></button>
                      <div className="min-w-0 flex-1">
                        <h2 className="text-[12px] font-semibold text-white truncate">{noteTitle(selectedNote)}</h2>
                        <p className="text-[9px] font-mono text-[#A78BFA]/40 mt-0.5 truncate">{selectedNote.path}</p>
                      </div>
                    </div>
                    {deleteConfirm === selectedNote.path ? (
                      <div className="flex items-center justify-between mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                        <span className="text-[11px] text-red-400">Apagar esta nota?</span>
                        <div className="flex items-center gap-1.5">
                          <button onClick={() => deleteNote(selectedNote.path)} className="px-3 py-1 text-[10px] font-semibold rounded-md bg-red-500 text-white hover:bg-red-600">Apagar</button>
                          <button onClick={() => setDeleteConfirm(null)} className="px-3 py-1 text-[10px] font-medium rounded-md bg-white/10 text-white/60 border border-white/10">Cancelar</button>
                        </div>
                      </div>
                    ) : (
                      <button onClick={() => setDeleteConfirm(selectedNote.path)} className="mt-1.5 text-[10px] text-white/20 hover:text-red-400 transition-colors flex items-center gap-1">
                        <IconTrash size={10} /> Excluir nota
                      </button>
                    )}
                  </div>
                  <div className="flex-1 overflow-y-auto px-5 py-4">
                    <article className="prose prose-sm prose-invert max-w-none text-white/80 whitespace-pre-wrap leading-relaxed text-[13px]">
                      {noteContent || "Sem conteúdo"}
                    </article>
                  </div>
                </>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-center px-8">
                  <div className="w-16 h-16 rounded-2xl bg-[#1E1B2E] flex items-center justify-center mb-4">
                    <CvAtlas size={28} />
                  </div>
                  <h3 className="font-display text-sm font-semibold text-white/60 mb-1">Selecione uma nota</h3>
                  <p className="text-[11px] text-[#A78BFA]/40 max-w-xs">Navegue pelas categorias ou use a busca.</p>
                </div>
              )}
            </div>
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
  const prevCategoryRef = useRef<string | null>(null);
  const dragRef = useRef<{ down: boolean; node: string | null }>({ down: false, node: null });

  const maybeInit = useCallback(() => {
    if (initDone.current || !data.nodes.length) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    if (rect.width < 50 || rect.height < 50) return;

    const w = rect.width, h = rect.height;
    const cx = w / 2, cy = h / 2;
    const PADDING = 70;

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

    nodes.forEach((n) => {
      n.x = Math.max(40, Math.min(w - 40, n.x));
      n.y = Math.max(PADDING, Math.min(h - PADDING - 30, n.y));
    });

    nodesRef.current = nodes;

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

    // When category changes, re-spread visible nodes to avoid clumping
    if (activeCategory !== prevCategoryRef.current && nodesRef.current.length > 0) {
      prevCategoryRef.current = activeCategory;
      const rect2 = canvas.getBoundingClientRect();
      const cw = rect2.width, ch = rect2.height;
      const visible = activeCategory ? nodesRef.current.filter((n: any) => n.category === activeCategory) : nodesRef.current;
      if (visible.length > 0) {
        // Spread visible nodes in a circle, accounting for top category bar
        const cx2 = cw / 2, cy2 = ((ch - 55) / 2) + 40; // offset down for top bar
        const maxR = Math.min(cw, ch - 55 - 40) * 0.33;
        visible.forEach((n: any, i: number) => {
          const angle = (i / visible.length) * Math.PI * 2;
          const r = maxR * (0.4 + 0.6 * Math.random());
          n.x = cx2 + Math.cos(angle) * r;
          n.y = cy2 + Math.sin(angle) * r;
          n.vx = 0; n.vy = 0;
          // Clamp with padding
          n.x = Math.max(40, Math.min(cw - 40, n.x));
          n.y = Math.max(55, Math.min(ch - 75, n.y)); // 55px top for category bar
        });
      }
    }

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

    ctx.fillStyle = isDark ? "#0a0a09" : "#f5f3ef";
    ctx.fillRect(0, 0, w, h);

    [w * 0.32, w * 0.68].forEach((gx) => {
      const g = ctx.createRadialGradient(gx, h * 0.48, 0, gx, h * 0.48, w * 0.22);
      g.addColorStop(0, isDark ? "rgba(212,165,116,0.025)" : "rgba(212,165,116,0.035)");
      g.addColorStop(1, "transparent");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    });

    ctx.beginPath();
    ctx.moveTo(w / 2, h * 0.12);
    ctx.bezierCurveTo(w / 2 - 3, h * 0.3, w / 2 + 3, h * 0.6, w / 2, h * 0.82);
    ctx.strokeStyle = isDark ? "rgba(42,42,40,0.6)" : "rgba(228,227,224,0.6)";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    // Breathing: subtle radial oscillation that returns to initial positions
    // breatheFactor oscillates between -1 and +1, multiplied by tiny amplitude
    const breatheFactor = Math.sin(t * 0.3);
    const BREATHE_AMP = 0.00003; // half of previous — barely visible
    // Safe area bounds (keep nodes well within visible area)
    const SAFE_LEFT = 60;
    const SAFE_RIGHT = w - 60;
    const SAFE_TOP = 70; // below category bar
    const SAFE_BOTTOM = h - BOTTOM_PAD - 30;
    const centerX = w / 2;
    const centerY = (SAFE_TOP + SAFE_BOTTOM) / 2;

    for (const n of nodes) {
      const dx = n.x - centerX;
      const dy = n.y - centerY;
      const dist = Math.hypot(dx, dy) || 1;
      // Strong center pull to keep nodes contained
      const centerPull = 0.00012;
      n.vx += dx * centerPull;
      n.vy += dy * centerPull;
      // Breathing: radial push/pull that alternates (expands then contracts)
      n.vx += (dx / dist) * breatheFactor * BREATHE_AMP * dist;
      n.vy += (dy / dist) * breatheFactor * BREATHE_AMP * dist;
      // Node repulsion
      for (const o of nodes) {
        if (n.id === o.id) continue;
        const d = Math.hypot(n.x - o.x, n.y - o.y) || 1;
        if (d < 90) { const f = 500 / (d * d); n.vx += ((n.x - o.x) / d) * f * 0.25; n.vy += ((n.y - o.y) / d) * f * 0.25; }
      }
      // Boundary push-back forces (soft walls)
      if (n.x < SAFE_LEFT) n.vx += (SAFE_LEFT - n.x) * 0.05;
      if (n.x > SAFE_RIGHT) n.vx -= (n.x - SAFE_RIGHT) * 0.05;
      if (n.y < SAFE_TOP) n.vy += (SAFE_TOP - n.y) * 0.05;
      if (n.y > SAFE_BOTTOM) n.vy -= (n.y - SAFE_BOTTOM) * 0.05;

      n.vx *= 0.88; n.vy *= 0.88;
      n.x = Math.max(SAFE_LEFT, Math.min(SAFE_RIGHT, n.x + n.vx));
      n.y = Math.max(SAFE_TOP, Math.min(SAFE_BOTTOM, n.y + n.vy));
    }

    const isVisible = (n: any) => !activeCategory || n.category === activeCategory;

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
  const selectedNode = selectedBrainNode ? nodesRef.current.find((n) => n.id === selectedBrainNode) : null;

  return (
    <div ref={containerRef} className="flex-1 relative" style={{ minHeight: 400 }}>
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" style={{ touchAction: "none" }}
        onMouseMove={handleMouseMove} onMouseDown={handleMouseDown} onMouseUp={handleMouseUp}
        onMouseLeave={() => { dragRef.current = { down: false, node: null }; setHoveredNode(null); }}
        onDoubleClick={handleDoubleClick} />

      <button onClick={onBack}
        className="absolute top-3 left-3 px-2.5 py-1 text-[10px] font-medium rounded-md bg-[#111827]/90 backdrop-blur-sm border border-[#A78BFA]/20 text-[#A78BFA] hover:bg-[#1E1B2E] transition-colors flex items-center gap-1 z-20">
        <IconArrowLeft size={11} /> Voltar
      </button>

      <div className="absolute top-3 left-20 text-[9px] font-mono text-white/30 z-20">
        {data.nodes.length} nós
      </div>

      {/* Category filter bar — horizontal, top */}
      <div className="absolute top-11 left-0 right-0 flex items-center gap-1.5 px-3 z-20 overflow-x-auto">
        <button onClick={() => setActiveCategory(null)}
          className={`shrink-0 px-2 py-1 rounded-md text-[10px] font-medium transition-all border ${
            !activeCategory ? "bg-[#A78BFA]/20 border-[#A78BFA]/30 text-[#A78BFA]" : "bg-[#111827]/80 border-transparent text-white/30 hover:text-white/60"}`}>
          Tudo
        </button>
        {categories.map((cat) => (
          <button key={cat} onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
            className={`shrink-0 flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-all border ${
              activeCategory === cat ? "shadow-sm" : "bg-[#111827]/80 border-transparent text-white/30 hover:text-white/60"}`}
            style={activeCategory === cat ? { backgroundColor: hexToRgba(catColor(cat), 0.15), borderColor: hexToRgba(catColor(cat), 0.3), color: catColor(cat) } : {}}>
            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: catColor(cat) }} />
            {cat}
          </button>
        ))}
      </div>

      {selectedNode && (
        <div className="absolute bottom-4 right-4 w-56 bg-[#111827]/95 backdrop-blur-sm rounded-xl border border-[#A78BFA]/15 shadow-lg p-3 z-20">
          <div className="flex items-center justify-between mb-1.5">
            <h3 className="text-[12px] font-semibold text-white truncate pr-2">{selectedNode.label}</h3>
            <button onClick={() => setSelectedBrainNode(null)} className="text-white/30 hover:text-white shrink-0"><IconX size={12} /></button>
          </div>
          <div className="flex items-center gap-1.5 mb-2">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: catColor(selectedNode.category) }} />
            <span className="text-[9px] font-mono text-white/30">{selectedNode.path}</span>
          </div>
          <button onClick={() => {
            const note = notes.find((n) => n.path === selectedNode.path || n.path.endsWith(`/${selectedNode.id}.md`));
            if (note) onOpenNote(note);
          }} className="w-full px-3 py-1.5 text-[11px] font-medium rounded-lg bg-[#4ADE80]/10 text-[#4ADE80] hover:bg-[#4ADE80]/20 transition-colors">
            Abrir nota
          </button>
        </div>
      )}
    </div>
  );
}
