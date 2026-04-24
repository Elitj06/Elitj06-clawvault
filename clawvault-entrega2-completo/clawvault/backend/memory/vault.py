"""
ClawVault - Vault Estruturado (Segundo Cérebro)
================================================

Implementa a arquitetura "Raw / Wiki / Output" inspirada nas melhores
práticas do Obsidian + Hermes, mas adaptada para o ClawVault.

ESTRUTURA DO VAULT (tudo em markdown, legível fora do sistema):

  vault/
  ├── 00_raw/              📥 RAW INPUTS (não processados)
  │   ├── conversas/       (transcrições brutas)
  │   ├── artigos/         (web clippings, URLs)
  │   ├── documentos/      (PDFs, docs recebidos)
  │   └── audios/          (transcrições de áudio)
  │
  ├── 10_wiki/             🌐 CONHECIMENTO ESTRUTURADO
  │   ├── pessoas/         (perfis de pessoas mencionadas)
  │   ├── projetos/        (GymFlow, Marketplace Saúde, etc)
  │   ├── conceitos/       (arquiteturas, decisões técnicas)
  │   ├── empresas/        (concorrentes, parceiros)
  │   └── eventos/         (reuniões, marcos)
  │
  ├── 20_output/           📤 OUTPUTS GERADOS
  │   ├── drafts/          (rascunhos)
  │   ├── publicado/       (conteúdo entregue)
  │   └── descartado/      (tentativas abandonadas)
  │
  ├── 30_agents/           🤖 MEMÓRIA DOS AGENTES
  │   ├── _shared/         (memória compartilhada entre todos)
  │   ├── main/            (agente principal)
  │   ├── code-reviewer/   (cada sub-agente tem sua pasta)
  │   └── ...
  │
  ├── 40_skills/           ⚡ SKILLS COMO SABEDORIA
  │   └── ...
  │
  └── 99_index/            🗂️ ÍNDICES E LINKS
      ├── index.md         (MOC - Map of Content)
      ├── daily.md         (log diário do sistema)
      └── links.json       (grafo de conexões)

FILOSOFIA (inspirada em Karpathy + Hermes + Obsidian):
  - Raw: dados originais, nunca editados, fonte da verdade
  - Wiki: conhecimento CURADO, entidades com links [[entre]] elas
  - Output: produtos finais que você vai usar/publicar

Links wiki [[nome-da-pagina]] são automaticamente detectados
e formam um grafo de conhecimento navegável.
"""

import re
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.core.config import VAULT_DIR


# ==========================================================================
# ESTRUTURA DE DIRETÓRIOS
# ==========================================================================

# Usamos prefixos numéricos para manter ordem consistente
VAULT_STRUCTURE = {
    "raw": "00_raw",
    "raw_conversations": "00_raw/conversas",
    "raw_articles": "00_raw/artigos",
    "raw_documents": "00_raw/documentos",
    "raw_audios": "00_raw/audios",

    "wiki": "10_wiki",
    "wiki_people": "10_wiki/pessoas",
    "wiki_projects": "10_wiki/projetos",
    "wiki_concepts": "10_wiki/conceitos",
    "wiki_companies": "10_wiki/empresas",
    "wiki_events": "10_wiki/eventos",

    "output": "20_output",
    "output_drafts": "20_output/drafts",
    "output_published": "20_output/publicado",
    "output_discarded": "20_output/descartado",

    "agents": "30_agents",
    "agents_shared": "30_agents/_shared",

    "skills": "40_skills",

    "index": "99_index",
}


def ensure_vault_structure(vault_path: Path = VAULT_DIR) -> None:
    """Cria toda a estrutura de pastas do vault se não existir."""
    for _, relative in VAULT_STRUCTURE.items():
        (vault_path / relative).mkdir(parents=True, exist_ok=True)

    # Cria arquivo README inicial se não existe
    readme = vault_path / "README.md"
    if not readme.exists():
        readme.write_text(
            "# 🧠 Vault do ClawVault\n\n"
            "Este é seu segundo cérebro. Tudo aqui é markdown — você pode\n"
            "abrir no Obsidian, VS Code, ou qualquer editor de texto.\n\n"
            "## Estrutura\n\n"
            "- `00_raw/` — dados brutos (não edite)\n"
            "- `10_wiki/` — conhecimento estruturado com links [[entre]] páginas\n"
            "- `20_output/` — conteúdo que você vai publicar\n"
            "- `30_agents/` — memória dos agentes\n"
            "- `40_skills/` — skills e padrões aprendidos\n"
            "- `99_index/` — índices e grafo de conexões\n",
            encoding="utf-8",
        )

    # Cria índice inicial
    index_path = vault_path / VAULT_STRUCTURE["index"] / "index.md"
    if not index_path.exists():
        index_path.write_text(
            "# 🗂️ Index — Map of Content\n\n"
            "Este é o ponto de entrada do vault.\n"
            "Atualizado automaticamente pelo ClawVault.\n\n"
            f"*Gerado em {datetime.now():%Y-%m-%d %H:%M}*\n\n"
            "## Projetos ativos\n\n"
            "## Pessoas\n\n"
            "## Conceitos-chave\n\n",
            encoding="utf-8",
        )


# ==========================================================================
# FRONTMATTER (metadados YAML no topo de cada nota)
# ==========================================================================

@dataclass
class VaultNote:
    """Representa uma nota do vault com frontmatter + conteúdo."""
    title: str
    content: str
    layer: str = "wiki"                 # raw, wiki, output, agents
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)  # pessoas/projetos ligados
    source: Optional[str] = None        # URL, conversation_id, etc
    created: Optional[str] = None
    updated: Optional[str] = None
    agent: Optional[str] = None         # qual agente criou
    relevance: int = 5                  # 1-10, importa para priorização
    compressed: bool = False            # se já foi sumarizado
    extra: dict = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Serializa para markdown com frontmatter YAML."""
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        created = self.created or now
        updated = now

        fm_lines = ["---", f"title: {self.title}",
                    f"created: {created}", f"updated: {updated}",
                    f"layer: {self.layer}"]

        if self.tags:
            fm_lines.append(f"tags: [{', '.join(self.tags)}]")
        if self.entities:
            fm_lines.append(f"entities: [{', '.join(self.entities)}]")
        if self.source:
            fm_lines.append(f"source: {self.source}")
        if self.agent:
            fm_lines.append(f"agent: {self.agent}")
        if self.relevance != 5:
            fm_lines.append(f"relevance: {self.relevance}")
        if self.compressed:
            fm_lines.append("compressed: true")
        for k, v in self.extra.items():
            fm_lines.append(f"{k}: {v}")

        fm_lines.append("---")
        fm_lines.append("")
        fm_lines.append(self.content)

        return "\n".join(fm_lines)

    @classmethod
    def from_markdown(cls, text: str) -> "VaultNote":
        """Deserializa markdown com frontmatter."""
        metadata = {}
        content = text

        if text.startswith("---"):
            try:
                end = text.index("---", 3)
                fm = text[3:end].strip()
                content = text[end + 3:].strip()

                for line in fm.split("\n"):
                    if ":" in line:
                        k, _, v = line.partition(":")
                        k, v = k.strip(), v.strip()
                        # Parse de listas inline
                        if v.startswith("[") and v.endswith("]"):
                            v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
                        elif v.lower() in ("true", "false"):
                            v = v.lower() == "true"
                        elif v.isdigit():
                            v = int(v)
                        metadata[k] = v
            except ValueError:
                pass

        return cls(
            title=metadata.get("title", ""),
            content=content,
            layer=metadata.get("layer", "wiki"),
            tags=metadata.get("tags", []) if isinstance(metadata.get("tags"), list) else [],
            entities=metadata.get("entities", []) if isinstance(metadata.get("entities"), list) else [],
            source=metadata.get("source"),
            created=metadata.get("created"),
            updated=metadata.get("updated"),
            agent=metadata.get("agent"),
            relevance=metadata.get("relevance", 5),
            compressed=metadata.get("compressed", False),
        )


# ==========================================================================
# WIKI-LINKS ([[nome-da-pagina]])
# ==========================================================================

WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]")


def extract_wikilinks(content: str) -> list[str]:
    """Extrai todos os links [[entre-colchetes]] de um texto."""
    return [match.group(1).strip() for match in WIKILINK_RE.finditer(content)]


def resolve_wikilink(name: str, vault_path: Path = VAULT_DIR) -> Optional[Path]:
    """
    Procura um arquivo que corresponda a um wikilink.
    Primeiro tenta match exato, depois tenta normalizado.
    """
    name_clean = name.strip().replace("/", "-")

    # Busca em todo o vault
    for md_file in vault_path.rglob("*.md"):
        stem = md_file.stem
        if stem == name_clean or stem.lower() == name_clean.lower():
            return md_file

    # Busca por slug (nome normalizado)
    slug = name_clean.lower().replace(" ", "-")
    for md_file in vault_path.rglob("*.md"):
        if md_file.stem.lower() == slug:
            return md_file

    return None


# ==========================================================================
# VAULT MANAGER (interface principal)
# ==========================================================================

class Vault:
    """
    Gerenciador do vault estruturado. Interface para criar notas em
    qualquer camada, buscar, conectar entidades, etc.
    """

    def __init__(self, vault_path: Path = VAULT_DIR):
        self.vault_path = Path(vault_path)
        ensure_vault_structure(self.vault_path)

    # ----------------------------------------------------------------------
    # Criação de notas
    # ----------------------------------------------------------------------

    def _sanitize_filename(self, title: str) -> str:
        """Converte um título em nome de arquivo válido."""
        safe = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
        safe = re.sub(r"[\s]+", "-", safe).strip("-")
        return safe[:80] or "sem-titulo"

    def save_note(
        self,
        note: VaultNote,
        subfolder: Optional[str] = None,
    ) -> Path:
        """Salva uma nota na camada correspondente."""
        # Determina pasta base pela layer
        layer_map = {
            "raw": "00_raw",
            "wiki": "10_wiki",
            "output": "20_output",
            "agents": "30_agents",
            "skills": "40_skills",
        }
        base = self.vault_path / layer_map.get(note.layer, "10_wiki")

        if subfolder:
            base = base / subfolder
        base.mkdir(parents=True, exist_ok=True)

        # Nome do arquivo: data + título
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_prefix}_{self._sanitize_filename(note.title)}.md"
        filepath = base / filename

        # Se já existe com mesmo nome hoje, acrescenta sufixo
        counter = 1
        while filepath.exists():
            filename = f"{date_prefix}_{self._sanitize_filename(note.title)}-{counter}.md"
            filepath = base / filename
            counter += 1

        filepath.write_text(note.to_markdown(), encoding="utf-8")
        return filepath

    def save_raw(self, title: str, content: str,
                 source: Optional[str] = None,
                 subfolder: str = "conversas") -> Path:
        """Atalho: salva conteúdo bruto."""
        note = VaultNote(
            title=title, content=content, layer="raw",
            source=source, tags=["raw"],
        )
        return self.save_note(note, subfolder=subfolder)

    def save_wiki(self, title: str, content: str,
                  category: str = "conceitos",
                  entities: Optional[list[str]] = None,
                  tags: Optional[list[str]] = None) -> Path:
        """Atalho: salva nota wiki estruturada."""
        note = VaultNote(
            title=title, content=content, layer="wiki",
            tags=tags or [], entities=entities or [],
        )
        return self.save_note(note, subfolder=category)

    def save_output(self, title: str, content: str,
                    status: str = "drafts") -> Path:
        """Atalho: salva output gerado."""
        note = VaultNote(
            title=title, content=content, layer="output",
            tags=[status],
        )
        return self.save_note(note, subfolder=status)

    # ----------------------------------------------------------------------
    # Busca
    # ----------------------------------------------------------------------

    def search(self, query: str, layer: Optional[str] = None,
               limit: int = 10) -> list[dict]:
        """Busca notas por texto no conteúdo ou título."""
        results = []
        query_lower = query.lower()

        search_root = self.vault_path
        if layer:
            layer_map = {"raw": "00_raw", "wiki": "10_wiki",
                         "output": "20_output", "agents": "30_agents",
                         "skills": "40_skills"}
            if layer in layer_map:
                search_root = self.vault_path / layer_map[layer]

        for md_file in search_root.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if query_lower not in content.lower():
                    continue

                # Extrai snippet em volta do match
                idx = content.lower().find(query_lower)
                start = max(0, idx - 80)
                end = min(len(content), idx + 200)
                snippet = content[start:end].replace("\n", " ")

                results.append({
                    "path": str(md_file.relative_to(self.vault_path)),
                    "full_path": str(md_file),
                    "snippet": snippet,
                    "layer": self._detect_layer(md_file),
                })

                if len(results) >= limit:
                    break
            except Exception:
                continue

        return results

    def _detect_layer(self, path: Path) -> str:
        """Detecta em que camada uma nota está."""
        rel = path.relative_to(self.vault_path)
        first = rel.parts[0] if rel.parts else ""
        if first.startswith("00_"):
            return "raw"
        if first.startswith("10_"):
            return "wiki"
        if first.startswith("20_"):
            return "output"
        if first.startswith("30_"):
            return "agents"
        if first.startswith("40_"):
            return "skills"
        return "other"

    # ----------------------------------------------------------------------
    # Grafo de conhecimento
    # ----------------------------------------------------------------------

    def build_graph(self) -> dict:
        """
        Escaneia todo o vault e monta um grafo de conhecimento baseado em
        wiki-links [[entre-colchetes]].

        Retorna dict {nota: [notas_linkadas]}
        """
        graph = {}
        for md_file in self.vault_path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                links = extract_wikilinks(content)
                key = md_file.stem
                graph[key] = links
            except Exception:
                continue

        # Salva grafo em JSON para consulta rápida
        graph_path = self.vault_path / "99_index" / "links.json"
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        graph_path.write_text(
            json.dumps(graph, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return graph

    def find_backlinks(self, note_name: str) -> list[str]:
        """Acha todas as notas que linkam para esta."""
        graph = self.build_graph()
        return [source for source, links in graph.items()
                if note_name in links]

    def list_entities(self) -> dict[str, list[str]]:
        """
        Lista todas as entidades conhecidas no wiki, agrupadas por categoria.
        Útil para o agente saber "com quem/o quê" pode conectar informação.
        """
        entities = {
            "pessoas": [],
            "projetos": [],
            "conceitos": [],
            "empresas": [],
            "eventos": [],
        }

        for category in entities.keys():
            folder = self.vault_path / "10_wiki" / category
            if folder.exists():
                entities[category] = [f.stem for f in folder.glob("*.md")]

        return entities


# Instância global
vault = Vault()
