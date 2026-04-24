"""
ClawVault - Interface de Linha de Comando (CLI)
================================================

Comandos disponíveis:
    python -m backend.cli.main init           # Inicializa o banco
    python -m backend.cli.main chat           # Inicia chat interativo
    python -m backend.cli.main status         # Mostra status do sistema
    python -m backend.cli.main models         # Lista modelos disponíveis
    python -m backend.cli.main budget         # Mostra gastos do mês
    python -m backend.cli.main ask "pergunta" # Faz uma pergunta rápida
    python -m backend.cli.main search "termo" # Busca na memória

Para ver ajuda de qualquer comando: python -m backend.cli.main <comando> --help
"""

import sys
from pathlib import Path

# Adiciona raiz do projeto ao path (para permitir imports quando roda direto)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import click
from datetime import datetime

# Carrega .env ANTES de importar config
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from backend.core.config import MODELS_CATALOG, API_KEYS, APP_CONFIG, VAULT_DIR
from backend.core.database import db, get_monthly_spend
from backend.llm.router import router, LLMRequest
from backend.llm.classifier import classifier
from backend.memory.manager import memory
from backend.memory.vault import vault, VaultNote, ensure_vault_structure
from backend.memory.multi_agent import (
    AgentRegistry, get_agent_memory, shared_bus,
    ensure_multi_agent_schema, MemoryLevel,
)
from backend.compression import default_compressor, humanizer
from backend.importers import find_openclaw_installations, import_from_path, auto_import


# ==========================================================================
# HELPERS DE FORMATAÇÃO
# ==========================================================================

def _header(text: str) -> str:
    """Cria um cabeçalho visual."""
    return f"\n{'='*60}\n  {text}\n{'='*60}"


def _info(label: str, value: str) -> str:
    """Formata uma linha de informação."""
    return f"  {label:.<30} {value}"


def _color_tier(tier: str) -> str:
    """Retorna emoji por tier."""
    emojis = {"local": "🏠", "economy": "💰", "standard": "⭐", "premium": "🚀"}
    return emojis.get(tier, "•")


# ==========================================================================
# GRUPO PRINCIPAL
# ==========================================================================

@click.group()
@click.version_option(version=APP_CONFIG.version, prog_name="ClawVault")
def cli():
    """
    🐾 ClawVault - Sistema de agentes com memória e multi-LLM.

    Alternativa ao OpenClaw com foco em economia de tokens.
    """
    pass


# ==========================================================================
# COMANDO: INIT
# ==========================================================================

@cli.command()
def init():
    """Inicializa o banco de dados e estrutura do vault."""
    click.echo(_header("Inicializando ClawVault"))

    # 1. Banco de dados
    click.echo("📦 Criando banco de dados...")
    db.initialize()
    click.echo(f"   ✅ Banco criado em: {db.db_path}")

    # 2. Vault
    click.echo("\n📁 Criando vault estruturado (segundo cérebro)...")
    ensure_vault_structure(VAULT_DIR)
    click.echo(f"   ✅ Vault em: {VAULT_DIR}")
    click.echo(f"      📂 00_raw/       (dados brutos)")
    click.echo(f"      📂 10_wiki/      (conhecimento estruturado)")
    click.echo(f"      📂 20_output/    (conteúdo gerado)")
    click.echo(f"      📂 30_agents/    (memória dos agentes)")
    click.echo(f"      📂 40_skills/    (skills aprendidas)")
    click.echo(f"      📂 99_index/     (grafo de conexões)")

    # 2b. Schema multi-agente
    click.echo("\n🤖 Criando schema multi-agente...")
    ensure_multi_agent_schema()
    click.echo("   ✅ Tabelas: agents, agent_memory, shared_memory, learning_log")

    # 2c. Registra agente principal se não existir
    if not AgentRegistry.get("main"):
        AgentRegistry.register(
            name="main",
            role="Assistente pessoal principal do Eliandro",
            is_main=True,
            system_prompt=(
                "Você é o assistente pessoal principal do Eliandro, empreendedor "
                "brasileiro. Pode delegar tarefas específicas para sub-agentes "
                "especializados quando fizer sentido. Sempre responda em português."
            ),
        )
        click.echo("   ✅ Agente principal 'main' registrado")

    # 3. Verifica chaves de API
    click.echo("\n🔑 Verificando chaves de API...")
    providers_ok = []
    providers_missing = []

    for provider_name, key in [
        ("Anthropic (Claude)", API_KEYS.anthropic),
        ("OpenAI (GPT)", API_KEYS.openai),
        ("Google (Gemini)", API_KEYS.google),
        ("DeepSeek", API_KEYS.deepseek),
        ("Z.ai (GLM)", API_KEYS.zai),
        ("Groq (ultra rápido)", API_KEYS.groq),
        ("Moonshot (Kimi)", API_KEYS.moonshot),
        ("MiniMax", API_KEYS.minimax),
        ("Alibaba (Qwen)", API_KEYS.alibaba),
        ("OpenRouter (300+ modelos)", API_KEYS.openrouter),
    ]:
        if key:
            providers_ok.append(provider_name)
            click.echo(f"   ✅ {provider_name}")
        else:
            providers_missing.append(provider_name)
            click.echo(f"   ⚠️  {provider_name} — chave não configurada")

    if not providers_ok:
        click.echo(click.style(
            "\n⚠️  ATENÇÃO: Nenhuma chave de API configurada!\n"
            "Copie .env.example para .env e adicione pelo menos uma chave.",
            fg="yellow"
        ))
    else:
        click.echo(click.style(
            f"\n✅ ClawVault pronto! {len(providers_ok)} provider(s) configurado(s).",
            fg="green", bold=True
        ))
        click.echo("\nPróximo passo: python -m backend.cli.main chat")


# ==========================================================================
# COMANDO: STATUS
# ==========================================================================

@cli.command()
def status():
    """Mostra status geral do sistema."""
    click.echo(_header(f"ClawVault {APP_CONFIG.version} - Status"))

    # Providers
    click.echo("\n🔌 Providers configurados:")
    for name, key in [
        ("Anthropic", API_KEYS.anthropic),
        ("OpenAI", API_KEYS.openai),
        ("Google", API_KEYS.google),
        ("DeepSeek", API_KEYS.deepseek),
        ("Z.ai", API_KEYS.zai),
        ("Groq", API_KEYS.groq),
        ("Moonshot (Kimi)", API_KEYS.moonshot),
        ("MiniMax", API_KEYS.minimax),
        ("Alibaba (Qwen)", API_KEYS.alibaba),
        ("OpenRouter", API_KEYS.openrouter),
    ]:
        status_str = "✅ ativo" if key else "⚪ sem chave"
        click.echo(_info(name, status_str))
    click.echo(_info("Ollama (local)", f"✅ {API_KEYS.ollama_host}"))

    # Orçamento
    spend = get_monthly_spend()
    click.echo(f"\n💰 Orçamento do mês ({spend['year_month']}):")
    used_pct = (spend['spent_usd'] / APP_CONFIG.monthly_budget_usd * 100) if APP_CONFIG.monthly_budget_usd else 0
    click.echo(_info("Gasto atual", f"${spend['spent_usd']:.4f}"))
    click.echo(_info("Orçamento mensal", f"${APP_CONFIG.monthly_budget_usd:.2f}"))
    click.echo(_info("Uso", f"{used_pct:.1f}%"))

    # Conversas
    total_conv = db.fetch_one("SELECT COUNT(*) as n FROM conversations")
    total_msg = db.fetch_one("SELECT COUNT(*) as n FROM messages")
    click.echo("\n📊 Estatísticas:")
    click.echo(_info("Conversas", str(total_conv["n"] if total_conv else 0)))
    click.echo(_info("Mensagens", str(total_msg["n"] if total_msg else 0)))
    click.echo(_info("Vault", str(VAULT_DIR)))


# ==========================================================================
# COMANDO: MODELS
# ==========================================================================

@cli.command()
@click.option("--available-only", is_flag=True, help="Mostrar só modelos que têm API configurada")
def models(available_only: bool):
    """Lista todos os modelos LLM no catálogo."""
    click.echo(_header("Catálogo de Modelos LLM"))

    # Agrupar por tier
    from collections import defaultdict
    by_tier = defaultdict(list)
    for model in MODELS_CATALOG.values():
        if available_only and not API_KEYS.has_provider(model.provider):
            continue
        by_tier[model.tier.value].append(model)

    tier_order = ["premium", "standard", "economy", "local"]
    tier_names = {
        "premium": "🚀 PREMIUM (inteligência máxima)",
        "standard": "⭐ STANDARD (custo-benefício)",
        "economy": "💰 ECONOMY (barato e rápido)",
        "local": "🏠 LOCAL (grátis, roda no seu PC)",
    }

    for tier in tier_order:
        if tier not in by_tier:
            continue
        click.echo(f"\n{tier_names[tier]}")
        click.echo("-" * 60)
        for model in by_tier[tier]:
            available = "✅" if API_KEYS.has_provider(model.provider) else "⚪"
            cost_str = (
                "GRÁTIS" if model.cost_input == 0
                else f"${model.cost_input:.2f}/${model.cost_output:.2f}"
            )
            click.echo(f"  {available} {model.id:<22} {cost_str:<18} {model.provider}")
            click.echo(f"     {click.style(model.description, dim=True)}")


# ==========================================================================
# COMANDO: BUDGET
# ==========================================================================

@cli.command()
@click.option("--days", default=30, help="Quantidade de dias para analisar")
def budget(days: int):
    """Mostra gastos detalhados por modelo."""
    click.echo(_header(f"Gastos - Últimos {days} dias"))

    rows = db.fetch_all(
        """
        SELECT model_id, provider,
               COUNT(*) as calls,
               SUM(input_tokens) as in_tok,
               SUM(output_tokens) as out_tok,
               SUM(cost_usd) as total_cost
        FROM usage_log
        WHERE timestamp >= datetime('now', ? || ' days')
        GROUP BY model_id
        ORDER BY total_cost DESC
        """,
        (f"-{days}",),
    )

    if not rows:
        click.echo("\nℹ️  Sem uso registrado ainda.")
        return

    click.echo(f"\n{'Modelo':<22} {'Chamadas':>10} {'In tok':>12} {'Out tok':>12} {'Custo':>12}")
    click.echo("-" * 70)

    total_cost = 0
    for row in rows:
        click.echo(
            f"{row['model_id']:<22} "
            f"{row['calls']:>10} "
            f"{row['in_tok'] or 0:>12,} "
            f"{row['out_tok'] or 0:>12,} "
            f"${row['total_cost'] or 0:>10.4f}"
        )
        total_cost += row['total_cost'] or 0

    click.echo("-" * 70)
    click.echo(f"{'TOTAL':<58} ${total_cost:>10.4f}")


# ==========================================================================
# COMANDO: ASK (pergunta rápida)
# ==========================================================================

@cli.command()
@click.argument("question")
@click.option("--model", help="Forçar um modelo específico (ex: claude-opus-4-7)")
@click.option("--show-cost", is_flag=True, help="Mostrar custo da chamada")
def ask(question: str, model: str, show_cost: bool):
    """Faz uma pergunta rápida sem salvar em conversa."""
    click.echo(click.style(f"\n💭 {question}\n", fg="cyan"))

    # Classifica para mostrar ao usuário
    complexity, reason = classifier.classify_with_explanation(question)
    click.echo(click.style(
        f"🎯 Complexidade detectada: {complexity.name} ({reason})",
        dim=True
    ))

    request = LLMRequest(
        prompt=question,
        model_override=model,
    )

    response = router.route(request)

    if response.error:
        click.echo(click.style(f"\n❌ Erro: {response.error}", fg="red"))
        return

    click.echo(click.style(f"\n🤖 [{response.model_id}]", fg="green", bold=True))
    click.echo(response.content)

    if show_cost:
        click.echo(click.style(
            f"\n📊 {response.input_tokens} tokens in, {response.output_tokens} tokens out, "
            f"${response.cost_usd:.6f} ({response.duration_ms}ms)",
            dim=True
        ))


# ==========================================================================
# COMANDO: CHAT (interativo)
# ==========================================================================

@cli.command()
@click.option("--title", default=None, help="Título da conversa")
@click.option("--agent", default="default", help="Nome do agente")
@click.option("--system", default=None, help="System prompt customizado")
@click.option("--compress/--no-compress", default=True,
              help="Comprimir mensagens do usuário antes de enviar (default: ligado)")
def chat(title, agent, system, compress):
    """Inicia um chat interativo com memória persistente."""
    click.echo(_header(f"ClawVault - Chat Interativo ({agent})"))
    click.echo("Digite 'sair', 'exit' ou Ctrl+C para encerrar.")
    click.echo("Comandos especiais: /modelo, /custo, /limpar, /salvar, /economia\n")
    if compress:
        click.echo(click.style("💡 Compressão automática ATIVADA (economiza tokens)", dim=True))

    # Cria conversa
    conv_id = memory.create_conversation(title=title, agent_name=agent)

    default_system = system or (
        "Você é um assistente pessoal do Eliandro, empreendedor brasileiro. "
        "Responda em português, seja direto e prático. "
        "Se a pergunta for sobre código, entregue código funcional."
    )

    total_cost = 0.0
    total_tokens_saved = 0   # tokens economizados pela compressão
    total_original_tokens = 0  # tokens que teriam sido enviados sem compressão
    forced_model = None

    while True:
        try:
            user_input = click.prompt(click.style("Você", fg="blue", bold=True), type=str)
        except (KeyboardInterrupt, click.Abort):
            click.echo("\n\n👋 Até mais!")
            break

        if user_input.lower() in ("sair", "exit", "quit"):
            click.echo("\n👋 Até mais!")
            break

        # Comandos especiais
        if user_input.startswith("/modelo"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                forced_model = parts[1].strip()
                click.echo(click.style(f"   ✅ Modelo forçado: {forced_model}", fg="green"))
            else:
                forced_model = None
                click.echo(click.style("   ✅ Usando roteador automático", fg="green"))
            continue

        if user_input == "/custo":
            click.echo(click.style(f"   💰 Custo desta conversa: ${total_cost:.6f}", fg="yellow"))
            continue

        if user_input == "/economia":
            if total_original_tokens > 0:
                pct = total_tokens_saved / total_original_tokens * 100
                click.echo(click.style(
                    f"   💸 Compressão economizou {total_tokens_saved} tokens "
                    f"({pct:.1f}% do que seria enviado)",
                    fg="yellow"
                ))
            else:
                click.echo(click.style(
                    "   💸 Nenhuma estatística ainda (compressão desligada ou sem mensagens)",
                    dim=True
                ))
            continue

        if user_input == "/limpar":
            memory.hot.clear(conv_id)
            click.echo(click.style("   ✅ Memória quente limpa", fg="green"))
            continue

        if user_input.startswith("/salvar"):
            parts = user_input.split(maxsplit=1)
            new_title = parts[1] if len(parts) > 1 else f"Conversa {datetime.now():%Y-%m-%d %H:%M}"
            db.execute(
                "UPDATE conversations SET title = ? WHERE id = ?",
                (new_title, conv_id),
            )
            click.echo(click.style(f"   ✅ Conversa salva como: {new_title}", fg="green"))
            continue

        # ---------- COMPRESSÃO AUTOMÁTICA ----------
        # O usuário escreve natural, mas enviamos versão comprimida para o LLM
        effective_input = user_input
        compression_info = None

        if compress:
            result = default_compressor.compress(user_input)
            if result.tokens_saved_estimate > 2:  # só usa se economizar
                effective_input = result.compressed
                compression_info = result
                total_tokens_saved += result.tokens_saved_estimate
                total_original_tokens += (
                    result.tokens_saved_estimate +
                    len(result.compressed) // 4
                )

        # Pega contexto da memória
        context_messages = memory.get_context_for_llm(conv_id, token_budget=4000)

        request = LLMRequest(
            prompt=effective_input,  # usa a versão comprimida
            system=default_system,
            messages=context_messages,
            model_override=forced_model,
            conversation_id=conv_id,
        )

        # Classifica para mostrar
        complexity, _ = classifier.classify_with_explanation(effective_input)

        click.echo(click.style(f"   🎯 {complexity.name}", dim=True), nl=False)
        if compression_info and compression_info.tokens_saved_estimate > 2:
            click.echo(
                click.style(
                    f" | 📉 -{compression_info.tokens_saved_estimate}tok "
                    f"({compression_info.savings_percent}%)",
                    fg="cyan", dim=True,
                ),
                nl=False,
            )

        response = router.route(request)

        if response.error:
            click.echo(click.style(f"\n   ❌ Erro: {response.error}", fg="red"))
            continue

        # Salva ambas mensagens na memória (a versão ORIGINAL do usuário)
        memory.add_message(
            conv_id, "user", user_input,  # salva o original, não o comprimido
            input_tokens=response.input_tokens,
        )
        memory.add_message(
            conv_id, "assistant", response.content,
            model_used=response.model_id,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
        )

        total_cost += response.cost_usd

        click.echo(
            click.style(f" → {response.model_id}", fg="magenta", dim=True)
            + click.style(f" (${response.cost_usd:.6f})", dim=True)
        )
        click.echo(click.style("Claude", fg="green", bold=True) + ": " + response.content)
        click.echo()


# ==========================================================================
# COMANDO: SEARCH
# ==========================================================================

@cli.command()
@click.argument("query")
@click.option("--limit", default=5, help="Quantidade de resultados")
def search(query: str, limit: int):
    """Busca na memória (morna + fria)."""
    click.echo(_header(f"Busca: '{query}'"))

    results = memory.search(query)

    # Resultados da memória morna (SQLite)
    if results["warm"]:
        click.echo("\n🔥 Mensagens recentes (últimos 7 dias):")
        for idx, msg in enumerate(results["warm"][:limit], 1):
            preview = msg["content"][:150].replace("\n", " ")
            click.echo(f"\n  {idx}. [{msg['role']}] {msg['created_at']}")
            click.echo(f"     {preview}...")

    # Resultados do vault (fria)
    if results["cold"]:
        click.echo("\n❄️  Notas no vault:")
        for idx, note in enumerate(results["cold"][:limit], 1):
            click.echo(f"\n  {idx}. 📄 {note['path']}")
            click.echo(f"     ...{note['snippet']}...")

    if not results["warm"] and not results["cold"]:
        click.echo("\n😕 Nenhum resultado encontrado.")


# ==========================================================================
# COMANDO: IMPORT-OPENCLAW
# ==========================================================================

@cli.command("import-openclaw")
@click.option(
    "--path", "-p", default=None,
    help="Caminho da pasta do OpenClaw. Se omitido, tenta detectar automaticamente."
)
@click.option("--dry-run", is_flag=True, help="Apenas mostra o que seria importado, sem salvar")
def import_openclaw_cmd(path, dry_run):
    """Importa agentes, skills e memória de uma instalação do OpenClaw."""
    click.echo(_header("Importando agentes do OpenClaw"))

    if dry_run:
        click.echo(click.style("🔍 Modo dry-run: nada será salvo no banco\n", fg="yellow"))

    if path:
        # Importação de caminho específico
        click.echo(f"📂 Importando de: {path}\n")
        report = import_from_path(path, dry_run=dry_run)
        click.echo(report.summary())
    else:
        # Auto-detecção
        click.echo("🔎 Procurando instalações do OpenClaw...")
        installations = find_openclaw_installations()

        if not installations:
            click.echo(click.style(
                "\n❌ Nenhuma instalação do OpenClaw encontrada.\n"
                "\nLocais verificados:\n"
                "  - ~/.openclaw\n"
                "  - ~/openclaw-workspace\n"
                "  - ~/.config/openclaw\n"
                "  - /root/.openclaw\n"
                "  - /opt/openclaw\n"
                "  - %APPDATA%/openclaw (Windows)\n"
                "\nUse --path para especificar manualmente.",
                fg="red"
            ))
            return

        click.echo(click.style(
            f"✅ Encontrei {len(installations)} instalação(ões):\n", fg="green"
        ))
        for p in installations:
            click.echo(f"   📂 {p}")

        click.echo()
        if not click.confirm("Prosseguir com a importação?", default=True):
            click.echo("Cancelado.")
            return

        reports = auto_import(dry_run=dry_run)
        for rpt in reports:
            click.echo("\n" + rpt.summary())


# ==========================================================================
# COMANDO: SKILLS
# ==========================================================================

@cli.command()
@click.option("--source", help="Filtrar por origem (openclaw, native, custom)")
def skills(source: str):
    """Lista todas as skills e agentes importados/cadastrados."""
    click.echo(_header("Skills e Agentes"))

    if source:
        rows = db.fetch_all(
            "SELECT * FROM skills WHERE source LIKE ? ORDER BY name",
            (f"{source}%",),
        )
    else:
        rows = db.fetch_all("SELECT * FROM skills ORDER BY source, name")

    if not rows:
        click.echo("\n😕 Nenhuma skill cadastrada ainda.")
        click.echo("   Use 'import-openclaw' para importar do OpenClaw.")
        return

    # Agrupa por origem
    by_source = {}
    for row in rows:
        src = row.get("source") or "custom"
        by_source.setdefault(src, []).append(row)

    for src, items in by_source.items():
        source_emojis = {
            "openclaw": "📦",
            "openclaw-agent": "🤖",
            "native": "⭐",
            "custom": "🔧",
        }
        emoji = source_emojis.get(src, "•")
        click.echo(f"\n{emoji} {src.upper()} ({len(items)})")
        click.echo("-" * 60)

        for row in items:
            enabled = "✅" if row["enabled"] else "⚪"
            model = row.get("preferred_model") or "auto"
            desc = (row.get("description") or "")[:70]
            click.echo(f"  {enabled} {row['name']:<35} [{model}]")
            if desc:
                click.echo(click.style(f"     {desc}", dim=True))


# ==========================================================================
# COMANDO: COMPRESS-TEST
# ==========================================================================

@cli.command("compress-test")
@click.argument("text")
@click.option("--aggressive", is_flag=True, help="Usar compressão agressiva")
def compress_test(text: str, aggressive: bool):
    """Testa a compressão de um texto — mostra economia de tokens."""
    from backend.compression import aggressive_compressor, default_compressor

    click.echo(_header("Teste de Compressão"))

    compressor = aggressive_compressor if aggressive else default_compressor
    result = compressor.compress(text)

    click.echo(f"\n📝 Original ({len(result.original)} chars):")
    click.echo(click.style(f"   {result.original}", dim=True))

    click.echo(f"\n📦 Comprimido ({len(result.compressed)} chars):")
    click.echo(click.style(f"   {result.compressed}", fg="cyan"))

    click.echo(f"\n📊 Resultado:")
    click.echo(_info("Método", result.method))
    click.echo(_info("Chars economizados", str(result.chars_saved)))
    click.echo(_info("Tokens economizados (~)", str(result.tokens_saved_estimate)))
    click.echo(_info("Redução", f"{result.savings_percent}%"))
    if result.semantic_cost > 0:
        click.echo(_info("Custo da compressão", f"${result.semantic_cost:.6f}"))


# ==========================================================================
# COMANDO: AGENTS (gerenciar agentes)
# ==========================================================================

@cli.group()
def agents():
    """Gerencia agentes e sub-agentes do sistema."""
    pass


@agents.command("list")
def agents_list():
    """Lista todos os agentes registrados."""
    ensure_multi_agent_schema()
    all_agents = AgentRegistry.list_all()

    if not all_agents:
        click.echo("\n😕 Nenhum agente registrado ainda.")
        click.echo("   Use 'python -m backend.cli.main init' para criar o agente principal.")
        return

    click.echo(_header(f"Agentes registrados ({len(all_agents)})"))

    for ag in all_agents:
        marker = "🌟" if ag["is_main"] else "🤖"
        parent = f" ← {ag['parent_agent']}" if ag.get("parent_agent") else ""
        click.echo(f"\n  {marker} {click.style(ag['name'], bold=True)}{parent}")
        if ag.get("role"):
            click.echo(f"     📝 {ag['role']}")
        if ag.get("preferred_model"):
            click.echo(f"     🎯 Modelo: {ag['preferred_model']}")
        if ag.get("total_calls"):
            click.echo(f"     📊 {ag['total_calls']} chamadas, "
                       f"{ag.get('total_tokens', 0)} tokens")


@agents.command("create")
@click.argument("name")
@click.option("--role", required=True, help="Função do sub-agente")
@click.option("--parent", default="main", help="Agente pai (default: main)")
@click.option("--model", default=None, help="Modelo preferido")
@click.option("--prompt", default=None, help="System prompt customizado")
def agents_create(name, role, parent, model, prompt):
    """Cria um novo sub-agente."""
    ensure_multi_agent_schema()

    if AgentRegistry.get(name):
        click.echo(click.style(
            f"\n⚠️  Agente '{name}' já existe. Use agents update para modificar.",
            fg="yellow"
        ))
        return

    if not AgentRegistry.get(parent):
        click.echo(click.style(
            f"\n❌ Agente pai '{parent}' não existe.",
            fg="red"
        ))
        return

    system_prompt = prompt or (
        f"Você é o sub-agente '{name}' com a função: {role}. "
        "Responda de forma direta e objetiva em português."
    )

    AgentRegistry.register(
        name=name,
        role=role,
        parent_agent=parent,
        system_prompt=system_prompt,
        preferred_model=model,
    )
    click.echo(click.style(
        f"\n✅ Sub-agente '{name}' criado com sucesso!", fg="green"
    ))
    click.echo(f"   Pai: {parent}")
    click.echo(f"   Função: {role}")
    if model:
        click.echo(f"   Modelo: {model}")


@agents.command("show")
@click.argument("name")
def agents_show(name):
    """Mostra detalhes de um agente (incluindo memória)."""
    ensure_multi_agent_schema()
    ag = AgentRegistry.get(name)

    if not ag:
        click.echo(click.style(f"\n❌ Agente '{name}' não existe.", fg="red"))
        return

    click.echo(_header(f"Agente: {name}"))
    click.echo(_info("Função", ag.get("role", "?")))
    click.echo(_info("Pai", ag.get("parent_agent") or "(nenhum — é principal)"))
    click.echo(_info("Principal", "sim" if ag["is_main"] else "não"))
    click.echo(_info("Modelo preferido", ag.get("preferred_model") or "auto"))
    click.echo(_info("Criado em", str(ag.get("created_at", "?"))))
    click.echo(_info("Chamadas", str(ag.get("total_calls", 0))))

    # Estatísticas de memória
    mem = get_agent_memory(name)
    stats = mem.stats()
    click.echo("\n🧠 Memória progressiva:")
    for level in ("core", "learned", "episodic"):
        s = stats[level]
        emoji = {"core": "⭐", "learned": "📚", "episodic": "💭"}[level]
        click.echo(f"  {emoji} {level.upper():<10} "
                   f"{s['entries']} entradas, ~{s['tokens']} tokens")

    # Sub-agentes
    subs = AgentRegistry.list_subagents(name)
    if subs:
        click.echo(f"\n🔗 Sub-agentes ({len(subs)}):")
        for sub in subs:
            click.echo(f"  - {sub['name']}: {sub.get('role', '')}")


# ==========================================================================
# COMANDO: MEMORY (gerenciar memória de agentes)
# ==========================================================================

@cli.group()
def memory_cmd():
    """Gerencia memória progressiva dos agentes."""
    pass


# Registra como 'memory' no CLI (não pode chamar a função de 'memory' por conflito)
cli.commands["memory"] = memory_cmd


@memory_cmd.command("add")
@click.argument("agent_name")
@click.argument("key")
@click.argument("content")
@click.option("--level",
              type=click.Choice(["core", "learned", "episodic"]),
              default="learned", help="Nível da memória")
@click.option("--relevance", type=int, default=5, help="Relevância (1-10)")
def memory_add(agent_name, key, content, level, relevance):
    """Adiciona uma memória a um agente."""
    if not AgentRegistry.get(agent_name):
        click.echo(click.style(f"\n❌ Agente '{agent_name}' não existe.", fg="red"))
        return

    mem = get_agent_memory(agent_name)
    if level == "core":
        mem.add_core(key, content, relevance)
    elif level == "learned":
        mem.add_learned(key, content, relevance=relevance)
    else:
        mem.add_episodic(content)

    click.echo(click.style(
        f"\n✅ Memória adicionada ao agente '{agent_name}' (nível: {level})",
        fg="green"
    ))


@memory_cmd.command("show")
@click.argument("agent_name")
@click.option("--level",
              type=click.Choice(["core", "learned", "episodic", "all"]),
              default="all", help="Nível a mostrar")
def memory_show(agent_name, level):
    """Mostra memórias de um agente."""
    if not AgentRegistry.get(agent_name):
        click.echo(click.style(f"\n❌ Agente '{agent_name}' não existe.", fg="red"))
        return

    click.echo(_header(f"Memória do agente '{agent_name}'"))

    levels = ["core", "learned", "episodic"] if level == "all" else [level]

    for lv in levels:
        rows = db.fetch_all(
            """
            SELECT * FROM agent_memory
            WHERE agent_name = ? AND level = ?
            ORDER BY relevance DESC, usage_count DESC
            """,
            (agent_name, lv),
        )

        emoji = {"core": "⭐", "learned": "📚", "episodic": "💭"}[lv]
        click.echo(f"\n{emoji} {lv.upper()} ({len(rows)} entradas)")

        if not rows:
            click.echo("   (vazio)")
            continue

        for row in rows[:15]:
            rel = "★" * row["relevance"] + "☆" * (10 - row["relevance"])
            used = f" [usado {row['usage_count']}x]" if row["usage_count"] else ""
            click.echo(f"  {rel} {click.style(row['key'], bold=True)}{used}")
            content_preview = row["content"][:120].replace("\n", " ")
            click.echo(click.style(f"     {content_preview}", dim=True))


@memory_cmd.command("share")
@click.argument("namespace")
@click.argument("key")
@click.argument("content")
@click.option("--source", default="main", help="Agente que está compartilhando")
@click.option("--targets", default=None,
              help="Agentes alvo (separados por vírgula). Omita para todos.")
@click.option("--ttl", type=int, default=None, help="TTL em horas (padrão: permanente)")
def memory_share(namespace, key, content, source, targets, ttl):
    """Publica memória compartilhada entre agentes."""
    target_list = [t.strip() for t in targets.split(",")] if targets else None

    shared_bus.publish(
        namespace=namespace,
        key=key,
        content=content,
        source_agent=source,
        target_agents=target_list,
        ttl_hours=ttl,
    )

    click.echo(click.style(
        f"\n✅ Memória publicada no canal '{namespace}'", fg="green"
    ))
    click.echo(f"   Chave: {key}")
    click.echo(f"   Fonte: {source}")
    if target_list:
        click.echo(f"   Alvos: {', '.join(target_list)}")
    else:
        click.echo(f"   Alvos: todos os agentes")


@memory_cmd.command("channels")
def memory_channels():
    """Lista todos os canais de memória compartilhada."""
    ensure_multi_agent_schema()
    channels = shared_bus.list_namespaces()

    if not channels:
        click.echo("\n😕 Nenhum canal de memória compartilhada ainda.")
        return

    click.echo(_header(f"Canais de memória compartilhada ({len(channels)})"))
    for ch in channels:
        click.echo(f"\n  📡 {click.style(ch['namespace'], bold=True)}")
        click.echo(f"     {ch['entries']} entradas, ~{ch['total_tokens']} tokens")
        click.echo(click.style(
            f"     Última atualização: {ch['last_updated']}", dim=True
        ))


@memory_cmd.command("forward")
@click.argument("from_ns")
@click.argument("to_ns")
@click.option("--keys", default=None, help="Chaves específicas (separadas por vírgula)")
def memory_forward(from_ns, to_ns, keys):
    """Encaminha memórias de um namespace para outro."""
    key_list = [k.strip() for k in keys.split(",")] if keys else None
    count = shared_bus.forward(from_ns, to_ns, keys=key_list)

    click.echo(click.style(
        f"\n✅ {count} memória(s) encaminhada(s) de '{from_ns}' para '{to_ns}'",
        fg="green"
    ))


# ==========================================================================
# COMANDO: VAULT (gerenciar o segundo cérebro)
# ==========================================================================

@cli.group()
def vault_cmd():
    """Gerencia o vault (segundo cérebro estilo Obsidian)."""
    pass


cli.commands["vault"] = vault_cmd


@vault_cmd.command("status")
def vault_status():
    """Mostra estatísticas do vault."""
    from backend.memory.vault import VAULT_STRUCTURE

    click.echo(_header("Status do Vault"))
    click.echo(f"📂 Localização: {VAULT_DIR}\n")

    total_files = 0
    total_size = 0

    for label, folder in VAULT_STRUCTURE.items():
        # Só mostra pastas principais (sem as subpastas)
        if "_" not in label.split("_")[0] and "_" in label:
            continue

        path = VAULT_DIR / folder
        if not path.exists():
            continue

        files = list(path.rglob("*.md"))
        count = len(files)
        size = sum(f.stat().st_size for f in files if f.is_file())
        total_files += count
        total_size += size

        if count > 0:
            click.echo(f"  📁 {folder:<25} {count:>4} arquivos  ({size // 1024} KB)")

    click.echo(f"\n{'TOTAL':<27} {total_files:>4} arquivos  ({total_size // 1024} KB)")


@vault_cmd.command("save")
@click.option("--title", required=True, help="Título da nota")
@click.option("--content", required=True, help="Conteúdo da nota")
@click.option("--layer",
              type=click.Choice(["raw", "wiki", "output"]),
              default="wiki", help="Camada do vault")
@click.option("--category", default="conceitos",
              help="Subpasta (para wiki: pessoas, projetos, conceitos, etc)")
@click.option("--tags", default="", help="Tags separadas por vírgula")
def vault_save(title, content, layer, category, tags):
    """Salva uma nota no vault."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    if layer == "wiki":
        filepath = vault.save_wiki(
            title=title, content=content,
            category=category, tags=tag_list,
        )
    elif layer == "raw":
        filepath = vault.save_raw(title=title, content=content)
    else:
        filepath = vault.save_output(title=title, content=content)

    click.echo(click.style(f"\n✅ Nota salva em:", fg="green"))
    click.echo(f"   {filepath}")


@vault_cmd.command("search")
@click.argument("query")
@click.option("--layer",
              type=click.Choice(["raw", "wiki", "output", "agents", "skills"]),
              default=None)
@click.option("--limit", default=10)
def vault_search(query, layer, limit):
    """Busca notas no vault."""
    results = vault.search(query, layer=layer, limit=limit)

    if not results:
        click.echo(f"\n😕 Nenhum resultado para '{query}'.")
        return

    click.echo(_header(f"Resultados para '{query}' ({len(results)})"))
    for r in results:
        layer_emoji = {
            "raw": "📥", "wiki": "🌐", "output": "📤",
            "agents": "🤖", "skills": "⚡",
        }.get(r["layer"], "📄")
        click.echo(f"\n  {layer_emoji} {r['path']}")
        click.echo(click.style(f"     ...{r['snippet']}...", dim=True))


@vault_cmd.command("graph")
def vault_graph():
    """Reconstrói o grafo de conhecimento (wiki-links)."""
    click.echo("🔗 Escaneando vault para construir grafo de conexões...")
    graph = vault.build_graph()

    total_nodes = len(graph)
    total_links = sum(len(links) for links in graph.values())
    click.echo(click.style(
        f"\n✅ Grafo construído: {total_nodes} notas, {total_links} links",
        fg="green"
    ))

    # Mostra top 5 notas mais conectadas
    if graph:
        from collections import Counter
        backlink_count = Counter()
        for source, links in graph.items():
            for link in links:
                backlink_count[link] += 1

        top = backlink_count.most_common(5)
        if top:
            click.echo("\n🌟 Notas mais referenciadas:")
            for name, count in top:
                click.echo(f"  {count:>3}x  [[{name}]]")


# ==========================================================================
# ENTRY POINT
# ==========================================================================

if __name__ == "__main__":
    cli()
