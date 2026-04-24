"""
ClawVault - Importador OpenClaw
================================

Importa agentes, skills e configurações de uma instalação OpenClaw
existente para o ClawVault, preservando tudo que você já construiu.

O OpenClaw guarda configurações em vários lugares. Este importador
detecta automaticamente e traz tudo:

ESTRUTURA TÍPICA DO OPENCLAW:
  ~/.openclaw/                  (Linux/Mac - local padrão)
  %APPDATA%/openclaw/           (Windows)
  /root/.openclaw/              (VPS como root)
  ~/openclaw-workspace/         (instalações custom)

O QUE É IMPORTADO:
  ✓ Skills (pastas com SKILL.md)
  ✓ Agentes (configurações em agents/)
  ✓ Memória (arquivos .md de MEMORY/)
  ✓ Configurações de modelo preferido
  ✓ Tools habilitadas
  ✓ CLAUDE.md / AGENT.md (instruções principais)

NÃO É IMPORTADO (por segurança):
  ✗ Chaves de API (você configura manualmente no .env)
  ✗ Tokens de autenticação
  ✗ Histórico de mensagens do WhatsApp/Telegram
"""

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.core.config import VAULT_DIR
from backend.core.database import db


# ==========================================================================
# ESTRUTURAS
# ==========================================================================

@dataclass
class ImportedSkill:
    """Skill importada do OpenClaw."""
    name: str
    description: str
    prompt_template: str
    tools: list[str] = field(default_factory=list)
    preferred_model: Optional[str] = None
    source_path: Optional[Path] = None


@dataclass
class ImportedAgent:
    """Agente importado do OpenClaw."""
    name: str
    role: str
    system_prompt: str
    preferred_model: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    source_path: Optional[Path] = None


@dataclass
class ImportReport:
    """Relatório final da importação."""
    openclaw_root: Path
    skills_found: int = 0
    skills_imported: int = 0
    agents_found: int = 0
    agents_imported: int = 0
    memory_files_imported: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Resumo legível do que foi importado."""
        lines = [
            f"📦 Importação OpenClaw concluída",
            f"   Origem: {self.openclaw_root}",
            f"",
            f"   Skills:       {self.skills_imported}/{self.skills_found} importadas",
            f"   Agentes:      {self.agents_imported}/{self.agents_found} importados",
            f"   Memória:      {self.memory_files_imported} arquivos",
        ]
        if self.warnings:
            lines.append(f"\n⚠️  Avisos ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                lines.append(f"   • {w}")
        if self.errors:
            lines.append(f"\n❌ Erros ({len(self.errors)}):")
            for e in self.errors[:5]:
                lines.append(f"   • {e}")
        if self.notes:
            lines.append(f"\n📝 Notas:")
            for n in self.notes:
                lines.append(f"   • {n}")
        return "\n".join(lines)


# ==========================================================================
# DETECTOR DE INSTALAÇÃO
# ==========================================================================

def find_openclaw_installations() -> list[Path]:
    """
    Procura instalações do OpenClaw em locais comuns.
    Retorna lista de caminhos encontrados.
    """
    candidates = []
    home = Path.home()

    # Locais padrão
    possible_paths = [
        home / ".openclaw",
        home / "openclaw-workspace",
        home / ".config" / "openclaw",
        Path("/root/.openclaw"),
        Path("/opt/openclaw"),
    ]

    # Windows: %APPDATA%
    import os
    appdata = os.environ.get("APPDATA")
    if appdata:
        possible_paths.append(Path(appdata) / "openclaw")

    for path in possible_paths:
        if path.exists() and path.is_dir():
            # Validação: precisa ter pelo menos uma das marcas do OpenClaw
            markers = ["skills", "agents", "AGENT.md", "CLAUDE.md",
                       "openclaw.json", "config.json", "workspace"]
            has_marker = any((path / m).exists() for m in markers)
            if has_marker:
                candidates.append(path)

    return candidates


# ==========================================================================
# PARSERS DE FORMATO
# ==========================================================================

def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Extrai frontmatter YAML-like de um arquivo markdown.
    Retorna (metadados, corpo_sem_frontmatter).
    """
    if not content.startswith("---"):
        return {}, content

    try:
        end = content.index("---", 3)
    except ValueError:
        return {}, content

    meta_block = content[3:end].strip()
    body = content[end + 3:].strip()

    metadata = {}
    for line in meta_block.split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"\'')
            # Parse simples de listas inline: [a, b, c]
            if val.startswith("[") and val.endswith("]"):
                val = [x.strip().strip('"\'') for x in val[1:-1].split(",") if x.strip()]
            metadata[key] = val

    return metadata, body


def _parse_skill_md(skill_path: Path) -> Optional[ImportedSkill]:
    """Parseia um arquivo SKILL.md no formato OpenClaw/Anthropic."""
    try:
        content = skill_path.read_text(encoding="utf-8")
    except Exception:
        return None

    metadata, body = _parse_frontmatter(content)

    name = metadata.get("name") or skill_path.parent.name
    description = metadata.get("description", "")

    # Se não tem description no frontmatter, pega primeira linha do corpo
    if not description:
        for line in body.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                description = line[:200]
                break

    tools = metadata.get("tools", []) or metadata.get("allowed-tools", [])
    if isinstance(tools, str):
        tools = [t.strip() for t in tools.split(",")]

    preferred_model = metadata.get("model") or metadata.get("preferred-model")

    return ImportedSkill(
        name=str(name),
        description=str(description),
        prompt_template=body,
        tools=tools if isinstance(tools, list) else [],
        preferred_model=preferred_model,
        source_path=skill_path,
    )


def _parse_agent_config(agent_path: Path) -> Optional[ImportedAgent]:
    """Parseia configuração de agente (JSON ou MD)."""

    # Formato 1: JSON (ex: agents/chief_of_staff.json)
    if agent_path.suffix == ".json":
        try:
            data = json.loads(agent_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        return ImportedAgent(
            name=data.get("name", agent_path.stem),
            role=data.get("role", ""),
            system_prompt=(
                data.get("system_prompt")
                or data.get("systemPrompt")
                or data.get("instructions", "")
            ),
            preferred_model=(
                data.get("model")
                or data.get("preferred_model")
            ),
            skills=data.get("skills", []) or data.get("tools", []),
            source_path=agent_path,
        )

    # Formato 2: MD com frontmatter (ex: agents/assistant.md)
    if agent_path.suffix == ".md":
        try:
            content = agent_path.read_text(encoding="utf-8")
        except Exception:
            return None

        metadata, body = _parse_frontmatter(content)

        return ImportedAgent(
            name=metadata.get("name", agent_path.stem),
            role=metadata.get("role", ""),
            system_prompt=body,
            preferred_model=metadata.get("model"),
            skills=metadata.get("skills", []) if isinstance(
                metadata.get("skills"), list
            ) else [],
            source_path=agent_path,
        )

    return None


# ==========================================================================
# MAPEAMENTO DE MODELOS OPENCLAW → CLAWVAULT
# ==========================================================================

# Converte nomes de modelo usados no OpenClaw para IDs do ClawVault
MODEL_NAME_MAP = {
    # Claude
    "claude-3-opus": "claude-opus-4-7",
    "claude-3-sonnet": "claude-sonnet-4-6",
    "claude-3-haiku": "claude-haiku-4-5",
    "claude-opus": "claude-opus-4-7",
    "claude-sonnet": "claude-sonnet-4-6",
    "claude-haiku": "claude-haiku-4-5",
    # GPT
    "gpt-4": "gpt-4o",
    "gpt-4-turbo": "gpt-4o",
    "gpt-3.5-turbo": "gpt-4o-mini",
    # Gemini
    "gemini-pro": "gemini-2.5-pro",
    "gemini-flash": "gemini-2.5-flash",
    # Outros comuns no OpenClaw
    "deepseek": "deepseek-v3",
    "qwen": "qwen3.6-plus",
    "kimi": "kimi-k2.5",
}


def _normalize_model_name(name: Optional[str]) -> Optional[str]:
    """Converte nome de modelo do OpenClaw para ID do ClawVault."""
    if not name:
        return None
    name_lower = name.lower().strip()
    # Match exato primeiro
    if name_lower in MODEL_NAME_MAP:
        return MODEL_NAME_MAP[name_lower]
    # Match parcial (ex: "claude-3-5-sonnet-latest" → sonnet)
    for key, value in MODEL_NAME_MAP.items():
        if key in name_lower:
            return value
    # Se nenhum match, mantém o nome original (pode ser ID direto do ClawVault)
    return name


# ==========================================================================
# IMPORTADOR PRINCIPAL
# ==========================================================================

class OpenClawImporter:
    """Importa uma instalação do OpenClaw para o ClawVault."""

    def __init__(self, openclaw_root: Path, dry_run: bool = False):
        self.root = Path(openclaw_root).resolve()
        self.dry_run = dry_run
        self.report = ImportReport(openclaw_root=self.root)

    # ----------------------------------------------------------------------
    # Skills
    # ----------------------------------------------------------------------

    def _find_skills(self) -> list[Path]:
        """Procura arquivos SKILL.md em múltiplos locais possíveis."""
        candidates = []

        search_dirs = [
            self.root / "skills",
            self.root / "workspace" / "skills",
            self.root / ".openclaw" / "skills",
        ]

        for d in search_dirs:
            if not d.exists():
                continue
            for skill_file in d.rglob("SKILL.md"):
                candidates.append(skill_file)
            # também aceita .claude/skills
            for skill_file in d.rglob(".claude/skills/*/SKILL.md"):
                if skill_file not in candidates:
                    candidates.append(skill_file)

        return candidates

    def _import_skill(self, skill: ImportedSkill) -> bool:
        """Salva skill no banco de dados do ClawVault."""
        if self.dry_run:
            return True

        try:
            # Converte tools para JSON
            tools_json = json.dumps(skill.tools) if skill.tools else None
            model = _normalize_model_name(skill.preferred_model)

            db.execute(
                """
                INSERT INTO skills
                (name, description, prompt_template, preferred_model,
                 tools_json, source, enabled)
                VALUES (?, ?, ?, ?, ?, 'openclaw', 1)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    prompt_template = excluded.prompt_template,
                    preferred_model = excluded.preferred_model,
                    tools_json = excluded.tools_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (skill.name, skill.description, skill.prompt_template,
                 model, tools_json),
            )
            return True
        except Exception as e:
            self.report.errors.append(f"Skill '{skill.name}': {e}")
            return False

    # ----------------------------------------------------------------------
    # Agentes
    # ----------------------------------------------------------------------

    def _find_agents(self) -> list[Path]:
        """Procura configurações de agentes."""
        candidates = []

        search_dirs = [
            self.root / "agents",
            self.root / "workspace" / "agents",
            self.root / ".claude" / "agents",
        ]

        for d in search_dirs:
            if not d.exists():
                continue
            for ext in ("*.json", "*.md"):
                candidates.extend(d.rglob(ext))

        # AGENT.md / CLAUDE.md no root também são agentes
        for main_file in ("AGENT.md", "CLAUDE.md", "agent.md", "claude.md"):
            p = self.root / main_file
            if p.exists() and p not in candidates:
                candidates.append(p)

        return candidates

    def _import_agent(self, agent: ImportedAgent) -> bool:
        """Salva agente como skill especial no banco."""
        if self.dry_run:
            return True

        try:
            model = _normalize_model_name(agent.preferred_model)
            skills_json = json.dumps(agent.skills) if agent.skills else None

            # Agentes são armazenados na tabela skills com nome prefixado
            db.execute(
                """
                INSERT INTO skills
                (name, description, prompt_template, preferred_model,
                 tools_json, source, enabled)
                VALUES (?, ?, ?, ?, ?, 'openclaw-agent', 1)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    prompt_template = excluded.prompt_template,
                    preferred_model = excluded.preferred_model,
                    tools_json = excluded.tools_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    f"agent:{agent.name}",
                    f"[AGENT] {agent.role}"[:200],
                    agent.system_prompt,
                    model,
                    skills_json,
                ),
            )
            return True
        except Exception as e:
            self.report.errors.append(f"Agent '{agent.name}': {e}")
            return False

    # ----------------------------------------------------------------------
    # Memória / Notas
    # ----------------------------------------------------------------------

    def _import_memory(self) -> int:
        """Copia arquivos de memória do OpenClaw para o vault do ClawVault."""
        if self.dry_run:
            # Conta sem copiar
            count = 0
            for memory_dir_name in ("Memory", "memory", "Notes", "notes", "Journal", "journal"):
                memory_dir = self.root / memory_dir_name
                if memory_dir.exists():
                    count += len(list(memory_dir.rglob("*.md")))
            return count

        target_dir = VAULT_DIR / "importado-openclaw"
        target_dir.mkdir(parents=True, exist_ok=True)

        copied = 0
        for memory_dir_name in ("Memory", "memory", "Notes", "notes", "Journal", "journal"):
            memory_dir = self.root / memory_dir_name
            if not memory_dir.exists():
                continue

            sub_target = target_dir / memory_dir_name.lower()
            sub_target.mkdir(parents=True, exist_ok=True)

            for md_file in memory_dir.rglob("*.md"):
                try:
                    # Preserva estrutura de subpastas
                    rel = md_file.relative_to(memory_dir)
                    dest = sub_target / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)

                    # Só copia se não existe ou se o original é mais novo
                    if not dest.exists() or md_file.stat().st_mtime > dest.stat().st_mtime:
                        shutil.copy2(md_file, dest)
                        copied += 1
                except Exception as e:
                    self.report.warnings.append(
                        f"Erro ao copiar {md_file.name}: {str(e)[:100]}"
                    )

        if copied > 0:
            self.report.notes.append(
                f"Arquivos de memória copiados para: {target_dir}"
            )

        return copied

    # ----------------------------------------------------------------------
    # Execução
    # ----------------------------------------------------------------------

    def run(self) -> ImportReport:
        """Executa a importação completa."""

        if not self.root.exists():
            self.report.errors.append(
                f"Pasta do OpenClaw não encontrada: {self.root}"
            )
            return self.report

        # 1. Skills
        skill_files = self._find_skills()
        self.report.skills_found = len(skill_files)
        for skill_file in skill_files:
            skill = _parse_skill_md(skill_file)
            if skill and self._import_skill(skill):
                self.report.skills_imported += 1
            elif not skill:
                self.report.warnings.append(
                    f"Não consegui parsear skill: {skill_file.name}"
                )

        # 2. Agentes
        agent_files = self._find_agents()
        self.report.agents_found = len(agent_files)
        for agent_file in agent_files:
            agent = _parse_agent_config(agent_file)
            if agent and self._import_agent(agent):
                self.report.agents_imported += 1
            elif not agent:
                self.report.warnings.append(
                    f"Não consegui parsear agente: {agent_file.name}"
                )

        # 3. Memória
        self.report.memory_files_imported = self._import_memory()

        # 4. Configurações
        self._import_settings()

        # 5. Nota de segurança sobre API keys
        self.report.notes.append(
            "Chaves de API NÃO foram importadas. Configure no .env manualmente."
        )

        return self.report

    def _import_settings(self) -> None:
        """Importa configurações gerais do OpenClaw (modelo padrão, etc)."""
        from backend.core.database import set_setting

        # Procura openclaw.json ou config.json
        for config_name in ("openclaw.json", "config.json"):
            config_path = self.root / config_name
            if not config_path.exists():
                continue

            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            if self.dry_run:
                self.report.notes.append(f"Encontrou config: {config_name} (dry-run)")
                continue

            # Extrai modelo padrão se existir
            default_model = (
                config.get("defaultModel")
                or config.get("default_model")
                or config.get("model")
            )
            if default_model:
                normalized = _normalize_model_name(default_model)
                set_setting("imported_default_model", normalized)
                self.report.notes.append(
                    f"Modelo padrão do OpenClaw: {default_model} → {normalized}"
                )

            # Flags úteis
            for flag_name in ("autonomousMode", "tools_enabled", "web_search"):
                if flag_name in config:
                    set_setting(f"openclaw_{flag_name}", config[flag_name])
            break


# ==========================================================================
# API DE ALTO NÍVEL
# ==========================================================================

def import_from_path(
    openclaw_path: str | Path,
    dry_run: bool = False,
) -> ImportReport:
    """Função de conveniência — importa uma instalação específica."""
    importer = OpenClawImporter(Path(openclaw_path), dry_run=dry_run)
    return importer.run()


def auto_import(dry_run: bool = False) -> list[ImportReport]:
    """Detecta e importa todas as instalações do OpenClaw encontradas."""
    installations = find_openclaw_installations()
    if not installations:
        return []

    reports = []
    for path in installations:
        importer = OpenClawImporter(path, dry_run=dry_run)
        reports.append(importer.run())

    return reports
