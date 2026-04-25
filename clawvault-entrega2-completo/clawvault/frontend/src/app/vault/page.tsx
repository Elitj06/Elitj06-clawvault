"use client";

import { useState, useEffect, useRef } from "react";
import {
  Search,
  FolderOpen,
  FileText,
  Network,
  Tag,
  Calendar,
  ChevronRight,
  ChevronDown,
  Eye,
  GitBranch,
  Plus,
  ArrowLeft,
} from "lucide-react";
import { api } from "@/lib/api";

interface VaultLayer {
  key: string;
  label: string;
  icon: string;
  count: number;
  children?: { key: string; label: string; count: number }[];
}

interface NotePreview {
  path: string;
  title: string;
  snippet: string;
  layer: string;
  tags: string[];
  date?: string;
}

type ViewMode = "tree" | "graph";

export default function VaultPage() {
  const [layers, setLayers] = useState<VaultLayer[]>([]);
  const [notes, setNotes] = useState<NotePreview[]>([]);
  const [selectedNote, setSelectedNote] = useState<NotePreview | null>(null);
  const [noteContent, setNoteContent] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<NotePreview[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>("tree");
  const [expandedLayers, setExpandedLayers] = useState<Set<string>>(new Set(["10_wiki"]));
  const [graphData, setGraphData] = useState<{ nodes: any[]; edges: any[] } | null>(null);

  // Load vault status
  useEffect(() => {
    api.vaultStatus().then((data) => {
      const parsed: VaultLayer[] = [
        {
          key: "00_raw",
          label: "Dados brutos",
          icon: "📥",
          count: data.raw?.count || 0,
          children: [
            { key: "raw_conversations", label: "Conversas", count: data.raw_conversations?.count || 0 },
          ],
        },
        {
          key: "10_wiki",
          label: "Wiki (conhecimento)",
          icon: "📚",
          count: data.wiki?.count || 0,
          children: [
            { key: "wiki_projects", label: "Projetos", count: data.wiki_projects?.count || 0 },
            { key: "wiki_concepts", label: "Conceitos", count: data.wiki_concepts?.count || 0 },
            { key: "wiki_events", label: "Eventos", count: data.wiki_events?.count || 0 },
            { key: "wiki_people", label: "Pessoas", count: data.wiki_people?.count || 0 },
          ],
        },
        {
          key: "20_output",
          label: "Outputs",
          icon: "📝",
          count: data.output?.count || 0,
        },
        {
          key: "30_agents",
          label: "Agentes",
          icon: "🤖",
          count: data.agents?.count || 0,
        },
        {
          key: "99_index",
          label: "Índices",
          icon: "🗂️",
          count: data.index?.count || 0,
        },
      ];
      setLayers(parsed);
    });

    // Load all notes via search (empty query returns all)
    loadAllNotes();
  }, []);

  async function loadAllNotes() {
    try {
      const data = await api.vaultSearch("*");
      const results: NotePreview[] = (data.results || []).map((r: any) => ({
        path: r.path,
        title: r.path.split("/").pop()?.replace(".md", "") || r.path,
        snippet: r.snippet || "",
        layer: r.layer || "",
        tags: [],
      }));
      setNotes(results);
    } catch {
      setNotes([]);
    }
  }

  async function search(q: string) {
    setSearchQuery(q);
    if (!q.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      const data = await api.vaultSearch(q);
      setSearchResults(
        (data.results || []).map((r: any) => ({
          path: r.path,
          title: r.path.split("/").pop()?.replace(".md", "") || r.path,
          snippet: r.snippet || "",
          layer: r.layer || "",
          tags: [],
        }))
      );
    } catch {
      setSearchResults([]);
    }
  }

  async function openNote(note: NotePreview) {
    setSelectedNote(note);
    try {
      const data = await api.vaultReadNote(note.path);
      // Strip YAML frontmatter for display
      let content = data.content || "";
      if (content.startsWith("---")) {
        const parts = content.split("---", 2);
        if (parts.length >= 2) {
          content = content.slice(content.indexOf("---", 3) + 3).trim();
        }
      }
      setNoteContent(content);
    } catch {
      setNoteContent(note.snippet || "Erro ao carregar nota");
    }
  }

  async function loadGraph() {
    try {
      const data = await api.vaultGraph();
      setGraphData(data);
      setViewMode("graph");
    } catch {
      setGraphData(null);
    }
  }

  function toggleLayer(key: string) {
    const next = new Set(expandedLayers);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setExpandedLayers(next);
  }

  // Filter notes by layer
  const displayNotes = searchQuery ? searchResults : notes;
  const totalNotes = layers.reduce((sum, l) => sum + l.count, 0);

  return (
    <div className="h-[calc(100vh-7rem)] lg:h-[calc(100vh-4rem)] flex flex-col animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 sm:mb-6 gap-2">
        <div>
          <div className="font-mono text-xs text-ink-500 dark:text-ink-400 uppercase tracking-wider mb-1">
            Vault
          </div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink-900 dark:text-ink-50">
            Base de conhecimento
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs sm:text-sm font-mono text-ink-600 dark:text-ink-400">
            {totalNotes} notas • {layers.filter((l) => l.count > 0).length} camadas
          </div>
          <button onClick={loadGraph} className="btn-secondary text-xs flex items-center gap-1.5">
            <Network size={14} />
            <span className="hidden sm:inline">Grafo</span>
          </button>
        </div>
      </div>

      {/* Main content: 3-panel layout */}
      <div className="flex-1 flex flex-col lg:flex-row gap-3 sm:gap-4 min-h-0">
        {/* Left panel: file tree — collapsible on mobile */}
        <div className="lg:w-72 card p-3 flex flex-col overflow-hidden shrink-0 lg:max-h-full max-h-48 lg:max-h-none">
          {/* Search */}
          <div className="mb-3">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-2.5 text-ink-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => search(e.target.value)}
                placeholder="Buscar no vault..."
                className="w-full pl-8 pr-3 py-2 text-sm border border-ink-200 dark:border-ink-700 rounded-md bg-white dark:bg-ink-800 text-ink-900 dark:text-ink-100 focus:outline-none focus:ring-2 focus:ring-accent-300"
              />
            </div>
          </div>

          {/* File tree */}
          <div className="flex-1 overflow-y-auto space-y-0.5 text-sm">
            {layers.map((layer) => (
              <div key={layer.key}>
                <button
                  onClick={() => toggleLayer(layer.key)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-ink-100 dark:hover:bg-ink-800 text-ink-700 dark:text-ink-300 transition-colors"
                >
                  {layer.children ? (
                    expandedLayers.has(layer.key) ? (
                      <ChevronDown size={14} />
                    ) : (
                      <ChevronRight size={14} />
                    )
                  ) : (
                    <span className="w-3.5" />
                  )}
                  <span>{layer.icon}</span>
                  <span className="flex-1 text-left truncate">{layer.label}</span>
                  <span className="text-xs font-mono text-ink-400 dark:text-ink-500">{layer.count}</span>
                </button>

                {expandedLayers.has(layer.key) && layer.children && (
                  <div className="ml-5 space-y-0.5">
                    {layer.children.map((child) => (
                      <button
                        key={child.key}
                        onClick={() => {
                          // Filter notes to this subfolder
                          const subfolder = child.key.replace("wiki_", "10_wiki/").replace("raw_", "00_raw/");
                          const filtered = notes.filter((n) => n.path.includes(subfolder));
                          if (filtered.length > 0) setSearchResults(filtered);
                          setSearchQuery(child.label);
                        }}
                        className="w-full flex items-center gap-2 px-2 py-1 rounded-md hover:bg-ink-100 dark:hover:bg-ink-800 text-ink-500 dark:text-ink-400 text-xs transition-colors"
                      >
                        <FolderOpen size={12} />
                        <span className="flex-1 text-left">{child.label}</span>
                        <span className="font-mono text-ink-400 dark:text-ink-500">{child.count}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Middle panel: note list */}
        <div className="lg:w-80 card p-3 flex flex-col overflow-hidden shrink-0 lg:max-h-full max-h-48 lg:max-h-none">
          <div className="text-xs font-semibold uppercase tracking-wider text-ink-400 dark:text-ink-500 mb-2 flex items-center gap-1.5">
            <FileText size={12} />
            {searchQuery ? `Resultados (${displayNotes.length})` : `Notas recentes (${displayNotes.length})`}
          </div>
          <div className="flex-1 overflow-y-auto space-y-0.5">
            {displayNotes.length === 0 && (
              <div className="text-sm text-ink-400 dark:text-ink-500 text-center py-8">
                {searchQuery ? "Nenhum resultado" : "Nenhuma nota"}
              </div>
            )}
            {displayNotes.map((note, i) => (
              <button
                key={i}
                onClick={() => openNote(note)}
                className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
                  selectedNote?.path === note.path
                    ? "bg-accent-50 dark:bg-accent-900/30 border border-accent-200 dark:border-accent-700"
                    : "hover:bg-ink-50 dark:hover:bg-ink-800"
                }`}
              >
                <div className="text-sm font-medium text-ink-800 dark:text-ink-200 truncate">
                  {note.title.replace(/^\d{4}-\d{2}-\d{2}_/, "")}
                </div>
                <div className="text-[10px] text-ink-400 dark:text-ink-500 font-mono truncate mt-0.5">
                  {note.path}
                </div>
                {note.snippet && (
                  <div className="text-xs text-ink-500 dark:text-ink-400 line-clamp-2 mt-1">
                    {note.snippet.slice(0, 100)}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Right panel: note preview */}
        <div className="flex-1 card p-6 flex flex-col overflow-hidden">
          {selectedNote ? (
            <>
              <div className="flex items-center gap-3 mb-4">
                <button
                  onClick={() => setSelectedNote(null)}
                  className="text-ink-400 dark:text-ink-500 hover:text-ink-700 dark:hover:text-ink-200"
                >
                  <ArrowLeft size={16} />
                </button>
                <div>
                  <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-ink-50">
                    {selectedNote.title.replace(/^\d{4}-\d{2}-\d{2}_/, "").replace(/-/g, " ")}
                  </h2>
                  <div className="text-xs font-mono text-ink-400 dark:text-ink-500 flex items-center gap-2 mt-0.5">
                    <span className="flex items-center gap-1">
                      <FolderOpen size={10} />
                      {selectedNote.layer}
                    </span>
                    <span>•</span>
                    <span>{selectedNote.path}</span>
                  </div>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto">
                <div className="prose prose-sm dark:prose-invert max-w-none text-ink-800 dark:text-ink-200 whitespace-pre-wrap">
                  {noteContent || selectedNote.snippet || "Sem conteúdo disponível"}
                </div>
              </div>
            </>
          ) : viewMode === "graph" && graphData ? (
            <GraphView data={graphData} onBack={() => setViewMode("tree")} />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-full bg-ink-50 dark:bg-ink-800 flex items-center justify-center mb-4">
                <Eye className="text-ink-300 dark:text-ink-600" size={28} />
              </div>
              <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-ink-50 mb-2">
                Selecione uma nota
              </h3>
              <p className="text-ink-500 dark:text-ink-400 text-sm max-w-sm">
                Clique em uma nota na lista para visualizar o conteúdo, ou use a busca para encontrar informações.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function GraphView({
  data,
  onBack,
}: {
  data: { nodes: any[]; edges: any[] };
  onBack: () => void;
}) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={onBack}
          className="text-ink-400 dark:text-ink-500 hover:text-ink-700 dark:hover:text-ink-200"
        >
          <ArrowLeft size={16} />
        </button>
        <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-ink-50">
          Grafo de conhecimento
        </h2>
        <span className="text-xs font-mono text-ink-400 dark:text-ink-500">
          {data.nodes.length} nós • {data.edges.length} conexões
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {data.nodes.map((node, i) => (
            <div
              key={i}
              className="px-3 py-2 bg-ink-50 dark:bg-ink-800 rounded-md text-sm text-ink-700 dark:text-ink-300 truncate border border-ink-100 dark:border-ink-700"
            >
              <span className="mr-1.5">📄</span>
              {node.label || node.id}
            </div>
          ))}
        </div>
        {data.edges.length > 0 && (
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-400 dark:text-ink-500 mb-2">
              Conexões
            </h3>
            {data.edges.map((edge, i) => (
              <div key={i} className="text-xs font-mono text-ink-500 dark:text-ink-400 flex items-center gap-1">
                <span className="text-ink-700 dark:text-ink-300">{edge.source}</span>
                <span>→</span>
                <span className="text-ink-700 dark:text-ink-300">{edge.target}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
