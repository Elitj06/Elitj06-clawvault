"""
ClawVault ↔ OpenClaw Bridge
============================

Ponte bidirecional para:
1. Transferir memória/conhecimento entre sistemas
2. Compartilhar aprendizados de agentes
3. Sincronizar contatos e decisões
4. Treinar agentes OpenClaw com dados do ClawVault

COMO FUNCIONA:
- OpenClaw grava memória em ~/.openclaw/workspace/memory/ e MEMORY.md
- ClawVault grava memória no vault/ (markdown wiki)
- Esta ponte lê de ambos e sincroniza

ENDPOINTS:
- POST /api/bridge/import   — Importa dados do OpenClaw pro ClawVault
- POST /api/bridge/export   — Exporta dados do ClawVault pro OpenClaw
- GET  /api/bridge/status   — Status da sincronização
- POST /api/bridge/sync     — Sincronização bidirecional completa
"""

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

# ==========================================================================
# CONFIGURAÇÃO
# ==========================================================================

OPENCLAW_WORKSPACE = Path(os.getenv("OPENCLAW_WORKSPACE", "/root/.openclaw/workspace"))
OPENCLAW_MEMORY = OPENCLAW_WORKSPACE / "memory"
OPENCLAW_MEMORY_MD = OPENCLAW_WORKSPACE / "MEMORY.md"
OPENCLAW_PROJECTS = OPENCLAW_WORKSPACE / "projects"

CLAWVAULT_ROOT = Path(__file__).parent.parent.parent
CLAWVAULT_VAULT = CLAWVAULT_ROOT / "vault"

bridge_router = APIRouter(prefix="/api/bridge", tags=["bridge"])


# ==========================================================================
# HELPERS
# ==========================================================================

def read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def list_files_recursive(directory: Path, pattern: str = "*.md") -> list[Path]:
    if not directory.exists():
        return []
    return list(directory.rglob(pattern))


def extract_sections(markdown: str) -> dict[str, str]:
    """Extrai seções de um markdown por headers ##."""
    sections = {}
    current_header = "root"
    current_lines = []

    for line in markdown.split("\n"):
        if line.startswith("## "):
            if current_lines:
                sections[current_header] = "\n".join(current_lines).strip()
            current_header = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_header] = "\n".join(current_lines).strip()

    return sections


def parse_daily_log(content: str) -> dict:
    """Parse a daily log file into structured sections.

    Args:
        content: Daily log markdown content.

    Returns:
        dict: {decisoes, feito, licoes, pendencias} — section strings.
    """
    sections = extract_sections(content)
    return {
        "decisoes": sections.get("Decisões", ""),
        "feito": sections.get("Feito", ""),
        "licoes": sections.get("Lições", ""),
        "pendencias": sections.get("Pendências", ""),
    }


# ==========================================================================
# IMPORT: OpenClaw → ClawVault
# ==========================================================================

@bridge_router.post("/import")
def import_from_openclaw():
    """
    Importa dados do workspace OpenClaw para o vault do ClawVault.
    
    - MEMORY.md → wiki/conceitos/openclaw-memory.md
    - memory/*.md → wiki/eventos/ (cada daily log vira nota)
    - projects/*/STATE.md → wiki/projetos/
    """
    imported = []

    # 1. MEMORY.md
    if OPENCLAW_MEMORY_MD.exists():
        content = read_file_safe(OPENCLAW_MEMORY_MD)
        if content:
            dest = CLAWVAULT_VAULT / "10_wiki" / "conceitos" / "openclaw-memory-geral.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            note = (
                f"---\ntitle: OpenClaw Memory (Geral)\n"
                f"created: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"source: openclaw\nlayer: wiki\ntags: [openclaw, memoria, sincronizado]\n---\n\n"
                f"# OpenClaw — Memória Geral\n\n{content}"
            )
            dest.write_text(note, encoding="utf-8")
            imported.append(f"MEMORY.md → {dest.relative_to(CLAWVAULT_VAULT)}")

    # 2. Daily logs
    if OPENCLAW_MEMORY.exists():
        for log_file in sorted(OPENCLAW_MEMORY.glob("*.md")):
            if log_file.name in ("README.md",):
                continue
            content = read_file_safe(log_file)
            if not content:
                continue

            parsed = parse_daily_log(content)
            dest = CLAWVAULT_VAULT / "10_wiki" / "eventos" / f"openclaw-{log_file.stem}.md"
            dest.parent.mkdir(parents=True, exist_ok=True)

            note = (
                f"---\ntitle: OpenClaw Log {log_file.stem}\n"
                f"created: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"source: openclaw/daily-log\nlayer: wiki\n"
                f"tags: [openclaw, log-diario, sincronizado]\n---\n\n"
                f"# OpenClaw — {log_file.stem}\n\n{content}"
            )
            dest.write_text(note, encoding="utf-8")
            imported.append(f"memory/{log_file.name} → {dest.relative_to(CLAWVAULT_VAULT)}")

    # 3. Project STATE files
    if OPENCLAW_PROJECTS.exists():
        for state_file in OPENCLAW_PROJECTS.rglob("STATE.md"):
            project_name = state_file.parent.name
            content = read_file_safe(state_file)
            if not content:
                continue

            dest = CLAWVAULT_VAULT / "10_wiki" / "projetos" / f"openclaw-{project_name}-state.md"
            dest.parent.mkdir(parents=True, exist_ok=True)

            note = (
                f"---\ntitle: Projeto {project_name} (OpenClaw)\n"
                f"created: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"source: openclaw/project\nlayer: wiki\n"
                f"tags: [openclaw, projeto, {project_name}, sincronizado]\n---\n\n"
                f"# Projeto: {project_name}\n\n{content}"
            )
            dest.write_text(note, encoding="utf-8")
            imported.append(f"projects/{project_name}/STATE.md → {dest.relative_to(CLAWVAULT_VAULT)}")

    # 4. Learnings
    learnings_dir = OPENCLAW_WORKSPACE / ".learnings"
    if learnings_dir.exists():
        for lf in learnings_dir.glob("*.md"):
            content = read_file_safe(lf)
            if not content:
                continue
            dest = CLAWVAULT_VAULT / "10_wiki" / "conceitos" / f"openclaw-learnings-{lf.stem}.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            note = (
                f"---\ntitle: Lições OpenClaw ({lf.stem})\n"
                f"created: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"source: openclaw/learnings\nlayer: wiki\n"
                f"tags: [openclaw, licoes, sincronizado]\n---\n\n"
                f"# Lições: {lf.stem}\n\n{content}"
            )
            dest.write_text(note, encoding="utf-8")
            imported.append(f".learnings/{lf.name} → {dest.relative_to(CLAWVAULT_VAULT)}")

    return {
        "status": "ok",
        "imported": imported,
        "total": len(imported),
    }


# ==========================================================================
# EXPORT: ClawVault → OpenClaw
# ==========================================================================

@bridge_router.post("/export")
def export_to_openclaw():
    """
    Exporta conhecimento do ClawVault para o workspace OpenClaw.
    
    - Vault wiki → arquivo de referência em workspace
    - Conhecimento estruturado → formato que agentes OpenClaw podem ler
    """
    exported = []

    # 1. Export vault wiki como referência consolidada
    wiki_notes = list_files_recursive(CLAWVAULT_VAULT / "10_wiki")
    if wiki_notes:
        consolidated = []
        consolidated.append(f"# ClawVault — Base de Conhecimento")
        consolidated.append(f"_Exportado em {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")

        for note_path in sorted(wiki_notes):
            content = read_file_safe(note_path)
            if content:
                rel = note_path.relative_to(CLAWVAULT_VAULT)
                consolidated.append(f"\n---\n## [[{note_path.stem}]] (de {rel})\n")
                # Skip YAML frontmatter
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                consolidated.append(content)

        dest = OPENCLAW_WORKSPACE / "clawvault-knowledge-base.md"
        dest.write_text("\n".join(consolidated), encoding="utf-8")
        exported.append(f"Vault wiki ({len(wiki_notes)} notas) → clawvault-knowledge-base.md")

    # 2. Export agent context (formatted for OpenClaw agent prompts)
    agents_data = []
    for agent_dir in sorted((CLAWVAULT_VAULT / "30_agents").rglob("*.md")):
        content = read_file_safe(agent_dir)
        if content:
            agents_data.append({"file": agent_dir.name, "content": content})

    if agents_data:
        dest = OPENCLAW_WORKSPACE / "clawvault-agents-context.md"
        lines = ["# ClawVault — Contexto de Agentes\n"]
        for ad in agents_data:
            lines.append(f"\n## {ad['file']}\n\n{ad['content']}")
        dest.write_text("\n".join(lines), encoding="utf-8")
        exported.append(f"Agentes ({len(agents_data)}) → clawvault-agents-context.md")

    return {
        "status": "ok",
        "exported": exported,
        "total": len(exported),
    }


# ==========================================================================
# STATUS
# ==========================================================================

@bridge_router.get("/status")
def bridge_status():
    """Status da ponte e contagem de dados em cada lado."""
    openclaw_logs = len(list_files_recursive(OPENCLAW_MEMORY, "*.md")) if OPENCLAW_MEMORY.exists() else 0
    openclaw_projects = len(list(OPENCLAW_PROJECTS.rglob("STATE.md"))) if OPENCLAW_PROJECTS.exists() else 0
    openclaw_has_memory = OPENCLAW_MEMORY_MD.exists()

    vault_wiki = len(list_files_recursive(CLAWVAULT_VAULT / "10_wiki"))
    vault_raw = len(list_files_recursive(CLAWVAULT_VAULT / "00_raw"))
    vault_agents = len(list_files_recursive(CLAWVAULT_VAULT / "30_agents"))
    vault_output = len(list_files_recursive(CLAWVAULT_VAULT / "20_output"))

    # Check last sync
    last_import_file = CLAWVAULT_VAULT / "10_wiki" / "conceitos" / "openclaw-memory-geral.md"
    last_export_file = OPENCLAW_WORKSPACE / "clawvault-knowledge-base.md"
    
    last_import = None
    last_export = None
    if last_import_file.exists():
        last_import = datetime.fromtimestamp(last_import_file.stat().st_mtime).isoformat()
    if last_export_file.exists():
        last_export = datetime.fromtimestamp(last_export_file.stat().st_mtime).isoformat()

    return {
        "openclaw": {
            "workspace": str(OPENCLAW_WORKSPACE),
            "memory_md": openclaw_has_memory,
            "daily_logs": openclaw_logs,
            "projects": openclaw_projects,
        },
        "clawvault": {
            "vault_root": str(CLAWVAULT_VAULT),
            "wiki_notes": vault_wiki,
            "raw_notes": vault_raw,
            "agent_notes": vault_agents,
            "output_notes": vault_output,
        },
        "sync": {
            "last_import": last_import,
            "last_export": last_export,
        },
    }


# ==========================================================================
# FULL SYNC (bidirecional)
# ==========================================================================

@bridge_router.post("/sync")
def full_sync():
    """Sincronização bidirecional: importa + exporta."""
    import_result = import_from_openclaw()
    export_result = export_to_openclaw()

    return {
        "status": "ok",
        "import": import_result,
        "export": export_result,
        "timestamp": datetime.now().isoformat(),
    }
