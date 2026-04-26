"""
ClawVault - Configuração Central
=================================

Este arquivo define todos os modelos de LLM suportados, seus custos,
e as regras do roteador inteligente. Edite aqui se quiser adicionar
novos modelos ou ajustar preços.

Custos em USD por 1 milhão de tokens (input/output).
Atualizado em: Abril 2026
"""

from dataclasses import dataclass, field

# Carrega .env ANTES de ler qualquer env var
try:
    from dotenv import load_dotenv
    from pathlib import Path
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass
from enum import Enum
from pathlib import Path
from typing import Optional
import os


# ==========================================================================
# DIRETÓRIOS BASE
# ==========================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
VAULT_DIR = BASE_DIR / "vault"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Criar diretórios se não existirem
for d in [VAULT_DIR, DATA_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "clawvault.db"


# ==========================================================================
# CLASSIFICAÇÃO DE COMPLEXIDADE DE TAREFAS
# ==========================================================================

class TaskComplexity(Enum):
    """
    Níveis de complexidade que o roteador usa para escolher o modelo.

    TRIVIAL: formatação, listagem, extração de dados simples, classificação
    SIMPLE:  resumos, perguntas factuais, tradução, busca em memória
    MEDIUM:  análise, código rotineiro, escrita estruturada, planejamento
    COMPLEX: arquitetura, decisões técnicas, debug profundo, raciocínio multi-passo
    CRITICAL: decisões de negócio, análise de investimento, código de produção crítico
    """
    TRIVIAL = 1
    SIMPLE = 2
    MEDIUM = 3
    COMPLEX = 4
    CRITICAL = 5


class ModelTier(Enum):
    """Categoria do modelo por capacidade/preço."""
    LOCAL = "local"       # Ollama, grátis mas limitado
    ECONOMY = "economy"   # Barato e rápido (Haiku, Gemini Flash, GPT-4o-mini)
    STANDARD = "standard" # Bom custo-benefício (Sonnet, GPT-4o, Gemini Pro)
    PREMIUM = "premium"   # Top de linha (Opus, GPT-5, Gemini Ultra)


# ==========================================================================
# CATÁLOGO DE MODELOS LLM
# ==========================================================================

@dataclass
class LLMModel:
    """Representa um modelo de LLM com suas características."""
    id: str                    # Identificador interno
    provider: str              # anthropic, openai, google, deepseek, ollama
    model_name: str            # Nome real da API (ex: claude-opus-4-7)
    tier: ModelTier
    context_window: int        # Tokens máximos de contexto
    max_output: int            # Tokens máximos de output
    cost_input: float          # USD por 1M tokens de input
    cost_output: float         # USD por 1M tokens de output
    supports_cache: bool = False  # Suporta prompt caching?
    supports_vision: bool = False
    supports_tools: bool = True
    description: str = ""


# Catálogo completo. Preços aproximados de abril/2026.
# IMPORTANTE: valide preços atuais na documentação oficial antes de usar em produção.
MODELS_CATALOG: dict[str, LLMModel] = {

    # ---------------------------- ANTHROPIC ---------------------------------
    "claude-opus-4-7": LLMModel(
        id="claude-opus-4-7",
        provider="anthropic",
        model_name="claude-opus-4-7",
        tier=ModelTier.PREMIUM,
        context_window=200_000,
        max_output=8_192,
        cost_input=15.0,
        cost_output=75.0,
        supports_cache=True,
        supports_vision=True,
        description="Claude Opus 4.7 — modelo mais inteligente da Anthropic"
    ),
    "claude-sonnet-4-6": LLMModel(
        id="claude-sonnet-4-6",
        provider="anthropic",
        model_name="claude-sonnet-4-6",
        tier=ModelTier.STANDARD,
        context_window=200_000,
        max_output=8_192,
        cost_input=3.0,
        cost_output=15.0,
        supports_cache=True,
        supports_vision=True,
        description="Claude Sonnet 4.6 — melhor custo-benefício da Anthropic"
    ),
    "claude-haiku-4-5": LLMModel(
        id="claude-haiku-4-5",
        provider="anthropic",
        model_name="claude-haiku-4-5-20251001",
        tier=ModelTier.ECONOMY,
        context_window=200_000,
        max_output=8_192,
        cost_input=0.80,
        cost_output=4.0,
        supports_cache=True,
        supports_vision=True,
        description="Claude Haiku 4.5 — rápido e econômico"
    ),

    # ---------------------------- OPENAI ------------------------------------
    # GPT-5 família (flagship 2026)
    "gpt-5": LLMModel(
        id="gpt-5",
        provider="openai",
        model_name="gpt-5",
        tier=ModelTier.PREMIUM,
        context_window=400_000,
        max_output=16_384,
        cost_input=1.25,
        cost_output=10.0,
        supports_cache=True,
        supports_vision=True,
        description="GPT-5 — flagship da OpenAI, 400k contexto"
    ),
    "gpt-5-mini": LLMModel(
        id="gpt-5-mini",
        provider="openai",
        model_name="gpt-5-mini",
        tier=ModelTier.STANDARD,
        context_window=400_000,
        max_output=16_384,
        cost_input=0.75,
        cost_output=4.50,
        supports_cache=True,
        supports_vision=True,
        description="GPT-5 Mini — versão menor do GPT-5, ótimo custo-benefício"
    ),
    "gpt-4.1": LLMModel(
        id="gpt-4.1",
        provider="openai",
        model_name="gpt-4.1",
        tier=ModelTier.PREMIUM,
        context_window=1_000_000,
        max_output=32_768,
        cost_input=2.0,
        cost_output=8.0,
        supports_cache=True,
        supports_vision=True,
        description="GPT-4.1 — 1M de contexto, ótimo para documentos longos"
    ),
    "gpt-4.1-nano": LLMModel(
        id="gpt-4.1-nano",
        provider="openai",
        model_name="gpt-4.1-nano",
        tier=ModelTier.ECONOMY,
        context_window=1_000_000,
        max_output=16_384,
        cost_input=0.10,
        cost_output=0.40,
        supports_cache=True,
        supports_vision=True,
        description="GPT-4.1 Nano — ultra barato, 1M de contexto"
    ),
    "gpt-4o": LLMModel(
        id="gpt-4o",
        provider="openai",
        model_name="gpt-4o",
        tier=ModelTier.STANDARD,
        context_window=128_000,
        max_output=16_384,
        cost_input=2.5,
        cost_output=10.0,
        supports_cache=True,
        supports_vision=True,
        description="GPT-4o — modelo multimodal da OpenAI"
    ),
    "gpt-4o-mini": LLMModel(
        id="gpt-4o-mini",
        provider="openai",
        model_name="gpt-4o-mini",
        tier=ModelTier.ECONOMY,
        context_window=128_000,
        max_output=16_384,
        cost_input=0.15,
        cost_output=0.60,
        supports_cache=True,
        supports_vision=True,
        description="GPT-4o Mini — barato e multimodal"
    ),
    "o3-mini": LLMModel(
        id="o3-mini",
        provider="openai",
        model_name="o3-mini",
        tier=ModelTier.STANDARD,
        context_window=200_000,
        max_output=100_000,
        cost_input=1.10,
        cost_output=4.40,
        supports_cache=True,
        supports_vision=False,
        description="o3-mini — modelo de raciocínio da OpenAI (reasoning)"
    ),

    # ---------------------------- GOOGLE ------------------------------------
    # Gemini 3 (geração mais recente)
    "gemini-3-pro": LLMModel(
        id="gemini-3-pro",
        provider="google",
        model_name="gemini-3-pro",
        tier=ModelTier.PREMIUM,
        context_window=2_000_000,
        max_output=16_384,
        cost_input=1.25,
        cost_output=10.0,
        supports_cache=True,
        supports_vision=True,
        description="Gemini 3 Pro — flagship do Google, 2M contexto"
    ),
    "gemini-3-flash": LLMModel(
        id="gemini-3-flash",
        provider="google",
        model_name="gemini-3-flash",
        tier=ModelTier.STANDARD,
        context_window=1_000_000,
        max_output=8_192,
        cost_input=0.30,
        cost_output=1.20,
        supports_cache=True,
        supports_vision=True,
        description="Gemini 3 Flash — rápido e capaz, 1M contexto"
    ),
    # Gemini 2.5 (ainda muito usado e mais barato)
    "gemini-2.5-pro": LLMModel(
        id="gemini-2.5-pro",
        provider="google",
        model_name="gemini-2.5-pro",
        tier=ModelTier.PREMIUM,
        context_window=2_000_000,
        max_output=8_192,
        cost_input=1.25,
        cost_output=5.0,
        supports_cache=True,
        supports_vision=True,
        description="Gemini 2.5 Pro — contexto gigante de 2M tokens"
    ),
    "gemini-2.5-flash": LLMModel(
        id="gemini-2.5-flash",
        provider="google",
        model_name="gemini-2.5-flash",
        tier=ModelTier.ECONOMY,
        context_window=1_000_000,
        max_output=8_192,
        cost_input=0.075,
        cost_output=0.30,
        supports_cache=True,
        supports_vision=True,
        description="Gemini 2.5 Flash — barato e rápido, contexto de 1M"
    ),
    "gemini-flash-lite": LLMModel(
        id="gemini-flash-lite",
        provider="google",
        model_name="gemini-2.5-flash-lite",
        tier=ModelTier.ECONOMY,
        context_window=1_000_000,
        max_output=8_192,
        cost_input=0.10,
        cost_output=0.40,
        supports_cache=False,
        supports_vision=True,
        description="Gemini Flash Lite — ultra barato para tarefas triviais"
    ),

    # ---------------------------- GROQ (inferência ultra rápida) ------------
    # Groq só hospeda modelos open-source (Llama, Qwen, gpt-oss, Kimi, MiniMax)
    # Vantagem: 300-1000 tokens/segundo (10x mais rápido que GPUs).
    # Tem free tier generoso (30 req/min sem cartão).
    "groq-llama-3.3-70b": LLMModel(
        id="groq-llama-3.3-70b",
        provider="groq",
        model_name="llama-3.3-70b-versatile",
        tier=ModelTier.STANDARD,
        context_window=128_000,
        max_output=4_096,
        cost_input=0.59,
        cost_output=0.79,
        supports_cache=False,
        supports_vision=False,
        description="Llama 3.3 70B no Groq — nível GPT-4o a 5x mais rápido"
    ),
    "groq-llama-3.1-8b": LLMModel(
        id="groq-llama-3.1-8b",
        provider="groq",
        model_name="llama-3.1-8b-instant",
        tier=ModelTier.ECONOMY,
        context_window=128_000,
        max_output=4_096,
        cost_input=0.05,
        cost_output=0.08,
        supports_cache=False,
        supports_vision=False,
        description="Llama 3.1 8B no Groq — o modelo mais barato de produção ($0.05/M)"
    ),
    "groq-llama-4-scout": LLMModel(
        id="groq-llama-4-scout",
        provider="groq",
        model_name="meta-llama/llama-4-scout-17b-16e-instruct",
        tier=ModelTier.STANDARD,
        context_window=128_000,
        max_output=4_096,
        cost_input=0.11,
        cost_output=0.34,
        supports_cache=False,
        supports_vision=True,
        description="Llama 4 Scout no Groq — multimodal, barato e rápido"
    ),
    "groq-gpt-oss-120b": LLMModel(
        id="groq-gpt-oss-120b",
        provider="groq",
        model_name="openai/gpt-oss-120b",
        tier=ModelTier.STANDARD,
        context_window=131_000,
        max_output=4_096,
        cost_input=0.15,
        cost_output=0.60,
        supports_cache=False,
        supports_vision=False,
        description="GPT-OSS 120B no Groq — modelo aberto da OpenAI, ultra rápido"
    ),
    "groq-gpt-oss-20b": LLMModel(
        id="groq-gpt-oss-20b",
        provider="groq",
        model_name="openai/gpt-oss-20b",
        tier=ModelTier.ECONOMY,
        context_window=131_000,
        max_output=4_096,
        cost_input=0.10,
        cost_output=0.50,
        supports_cache=False,
        supports_vision=False,
        description="GPT-OSS 20B no Groq — fastest model (~940 tok/s)"
    ),
    "groq-qwen3-32b": LLMModel(
        id="groq-qwen3-32b",
        provider="groq",
        model_name="qwen/qwen3-32b",
        tier=ModelTier.STANDARD,
        context_window=131_000,
        max_output=4_096,
        cost_input=0.29,
        cost_output=0.59,
        supports_cache=False,
        supports_vision=False,
        description="Qwen 3 32B no Groq — bom em raciocínio, rápido"
    ),
    "groq-kimi-k2": LLMModel(
        id="groq-kimi-k2",
        provider="groq",
        model_name="moonshotai/kimi-k2-instruct",
        tier=ModelTier.STANDARD,
        context_window=131_000,
        max_output=16_384,
        cost_input=1.0,
        cost_output=3.0,
        supports_cache=False,
        supports_vision=False,
        description="Kimi K2 no Groq — forte em código, hospedado na Groq"
    ),

    # ---------------------------- MOONSHOT (Kimi) ---------------------------
    # API direta da Moonshot AI (criadora do Kimi). Endpoint OpenAI-compatible.
    # Kimi é excelente para agentes de longo prazo e coding.
    "kimi-k2.6": LLMModel(
        id="kimi-k2.6",
        provider="moonshot",
        model_name="kimi-k2-0425",
        tier=ModelTier.PREMIUM,
        context_window=262_144,
        max_output=16_384,
        cost_input=0.80,
        cost_output=3.50,
        supports_cache=True,
        supports_vision=True,
        description="Kimi K2.6 — multimodal, agentes de longa duração, 262k contexto"
    ),
    "kimi-k2.5": LLMModel(
        id="kimi-k2.5",
        provider="moonshot",
        model_name="kimi-k2-0125",
        tier=ModelTier.STANDARD,
        context_window=262_144,
        max_output=16_384,
        cost_input=0.44,
        cost_output=2.0,
        supports_cache=True,
        supports_vision=True,
        description="Kimi K2.5 — agent swarm (até 100 sub-agentes), ótimo em código"
    ),
    "kimi-k2-instant": LLMModel(
        id="kimi-k2-instant",
        provider="moonshot",
        model_name="kimi-k2-instant",
        tier=ModelTier.ECONOMY,
        context_window=128_000,
        max_output=4_096,
        cost_input=0.60,
        cost_output=2.50,
        supports_cache=True,
        supports_vision=False,
        description="Kimi K2 Instant — versão rápida e barata"
    ),

    # ---------------------------- MINIMAX ----------------------------------
    # API direta da MiniMax. Endpoint OpenAI-compatible.
    # MiniMax M2.7 é excelente custo-benefício: ~94% da qualidade do GLM-5.1 por 1/5 do preço.
    "minimax-m2.7": LLMModel(
        id="minimax-m2.7",
        provider="minimax",
        model_name="MiniMax-M2.7",
        tier=ModelTier.STANDARD,
        context_window=1_000_000,
        max_output=4_096,
        cost_input=0.30,
        cost_output=1.20,
        supports_cache=True,
        supports_vision=False,
        description="MiniMax M2.7 — 94% da qualidade do GLM-5.1 por 1/5 do preço, 1M contexto"
    ),
    "minimax-m2.5": LLMModel(
        id="minimax-m2.5",
        provider="minimax",
        model_name="MiniMax-M2.5",
        tier=ModelTier.STANDARD,
        context_window=1_000_000,
        max_output=16_384,
        cost_input=0.28,
        cost_output=0.42,
        supports_cache=True,
        supports_vision=False,
        description="MiniMax M2.5 — 80% SWE-bench, muito barato, 1M contexto"
    ),
    "minimax-m2-lightning": LLMModel(
        id="minimax-m2-lightning",
        provider="minimax",
        model_name="MiniMax-M2-Lightning",
        tier=ModelTier.ECONOMY,
        context_window=200_000,
        max_output=8_192,
        cost_input=0.15,
        cost_output=0.30,
        supports_cache=False,
        supports_vision=False,
        description="MiniMax M2 Lightning — versão ultra rápida e barata"
    ),

    # ---------------------------- QWEN / ALIBABA (DashScope) ----------------
    # API oficial da Alibaba Cloud (DashScope). Endpoint OpenAI-compatible.
    # Qwen tem MUITAS versões: Plus (barato), Max (premium), Coder (código), Turbo (econômico).
    "qwen3.6-max-preview": LLMModel(
        id="qwen3.6-max-preview",
        provider="alibaba",
        model_name="qwen3.6-max-preview",
        tier=ModelTier.PREMIUM,
        context_window=256_000,
        max_output=32_768,
        cost_input=1.60,
        cost_output=6.40,
        supports_cache=True,
        supports_vision=True,
        description="Qwen 3.6 Max Preview — líder em 6 benchmarks de código"
    ),
    "qwen3.6-plus": LLMModel(
        id="qwen3.6-plus",
        provider="alibaba",
        model_name="qwen3.6-plus",
        tier=ModelTier.STANDARD,
        context_window=1_000_000,
        max_output=16_384,
        cost_input=0.29,
        cost_output=1.16,
        supports_cache=True,
        supports_vision=True,
        description="Qwen 3.6 Plus — 1M contexto, excelente custo-benefício"
    ),
    "qwen3-coder": LLMModel(
        id="qwen3-coder",
        provider="alibaba",
        model_name="qwen3-coder-plus",
        tier=ModelTier.STANDARD,
        context_window=1_000_000,
        max_output=16_384,
        cost_input=0.30,
        cost_output=1.20,
        supports_cache=True,
        supports_vision=False,
        description="Qwen 3 Coder — especializado em código, 70.6% SWE-bench"
    ),
    "qwen3-turbo": LLMModel(
        id="qwen3-turbo",
        provider="alibaba",
        model_name="qwen3-turbo",
        tier=ModelTier.ECONOMY,
        context_window=1_000_000,
        max_output=8_192,
        cost_input=0.05,
        cost_output=0.20,
        supports_cache=False,
        supports_vision=False,
        description="Qwen 3 Turbo — muito barato ($0.05/M), bom para tarefas leves"
    ),
    "qwen3-vl-plus": LLMModel(
        id="qwen3-vl-plus",
        provider="alibaba",
        model_name="qwen3-vl-plus",
        tier=ModelTier.STANDARD,
        context_window=128_000,
        max_output=8_192,
        cost_input=0.30,
        cost_output=1.20,
        supports_cache=True,
        supports_vision=True,
        description="Qwen 3 VL Plus — versão multimodal (entende imagens)"
    ),

    # ---------------------------- OPENROUTER --------------------------------
    # OpenRouter é um GATEWAY que dá acesso a 300+ modelos com UMA só chave.
    # Endpoint: https://openrouter.ai/api/v1 (100% OpenAI-compatible)
    #
    # Por que vale a pena além das APIs diretas?
    #  1. Modelos GRÁTIS subsidiados pelo OpenRouter (rate-limit: 20 req/min,
    #     ~200 req/dia por modelo).
    #  2. Fallback universal se a API direta cair.
    #  3. Acesso a modelos que não têm API fácil (Nemotron NVIDIA, Gemma, etc).
    #  4. Você pode usar QUALQUER ID via --model "openrouter/qualquer-coisa".
    #
    # Listamos abaixo SÓ os mais úteis. Para usar qualquer outro modelo
    # do OpenRouter, passe no formato: openrouter/<provider>/<modelo>
    # (ex: openrouter/anthropic/claude-opus-4.5, openrouter/x-ai/grok-4)

    # 🆓 Auto-router grátis (OpenRouter escolhe entre os grátis disponíveis)
    "openrouter-free-auto": LLMModel(
        id="openrouter-free-auto",
        provider="openrouter",
        model_name="openrouter/free",
        tier=ModelTier.ECONOMY,
        context_window=200_000,
        max_output=8_192,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="Auto-router GRÁTIS do OpenRouter (escolhe automaticamente)"
    ),

    # 🆓 Qwen3 Coder 480B GRÁTIS — melhor modelo grátis para código
    "or-qwen3-coder-480b-free": LLMModel(
        id="or-qwen3-coder-480b-free",
        provider="openrouter",
        model_name="qwen/qwen3-coder:free",
        tier=ModelTier.ECONOMY,
        context_window=262_144,
        max_output=8_192,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="Qwen3 Coder 480B via OpenRouter — GRÁTIS, melhor grátis p/ código"
    ),

    # 🆓 DeepSeek R1 GRÁTIS — modelo de raciocínio grátis
    "or-deepseek-r1-free": LLMModel(
        id="or-deepseek-r1-free",
        provider="openrouter",
        model_name="deepseek/deepseek-r1:free",
        tier=ModelTier.ECONOMY,
        context_window=128_000,
        max_output=8_192,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="DeepSeek R1 via OpenRouter — GRÁTIS, raciocínio forte"
    ),

    # 🆓 Llama 3.3 70B GRÁTIS — qualidade próxima de GPT-4o
    "or-llama-3.3-70b-free": LLMModel(
        id="or-llama-3.3-70b-free",
        provider="openrouter",
        model_name="meta-llama/llama-3.3-70b-instruct:free",
        tier=ModelTier.ECONOMY,
        context_window=128_000,
        max_output=8_192,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="Llama 3.3 70B via OpenRouter — GRÁTIS, qualidade GPT-4o"
    ),

    # 🆓 GPT-OSS 120B GRÁTIS — modelo aberto da OpenAI
    "or-gpt-oss-120b-free": LLMModel(
        id="or-gpt-oss-120b-free",
        provider="openrouter",
        model_name="openai/gpt-oss-120b:free",
        tier=ModelTier.ECONOMY,
        context_window=131_000,
        max_output=8_192,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="GPT-OSS 120B via OpenRouter — GRÁTIS, modelo aberto da OpenAI"
    ),

    # 🆓 NVIDIA Nemotron 3 Super — hybrid MoE com 262k contexto
    "or-nemotron-3-super-free": LLMModel(
        id="or-nemotron-3-super-free",
        provider="openrouter",
        model_name="nvidia/nemotron-3-super:free",
        tier=ModelTier.ECONOMY,
        context_window=262_000,
        max_output=8_192,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="NVIDIA Nemotron 3 Super — GRÁTIS, hybrid MoE, 262k contexto"
    ),

    # 🆓 Google Gemma 3 27B — bom para seguir instruções estruturadas
    "or-gemma-3-27b-free": LLMModel(
        id="or-gemma-3-27b-free",
        provider="openrouter",
        model_name="google/gemma-3-27b-it:free",
        tier=ModelTier.ECONOMY,
        context_window=128_000,
        max_output=8_192,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="Google Gemma 3 27B — GRÁTIS, ótimo para instruções estruturadas"
    ),

    # 🆓 Mistral Small 3.1 — multilingue, bom para tarefas leves
    "or-mistral-small-3.1-free": LLMModel(
        id="or-mistral-small-3.1-free",
        provider="openrouter",
        model_name="mistralai/mistral-small-3.1-24b-instruct:free",
        tier=ModelTier.ECONOMY,
        context_window=128_000,
        max_output=8_192,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="Mistral Small 3.1 24B — GRÁTIS, multilingue (ótimo em PT-BR)"
    ),

    # Grok 4 via OpenRouter (xAI — não tem fallback via outra API aqui)
    "or-grok-4": LLMModel(
        id="or-grok-4",
        provider="openrouter",
        model_name="x-ai/grok-4",
        tier=ModelTier.PREMIUM,
        context_window=2_000_000,
        max_output=16_384,
        cost_input=3.0,
        cost_output=15.0,
        supports_cache=True,
        supports_vision=True,
        description="Grok 4 via OpenRouter — 2M contexto, acesso a dados do X"
    ),

    # Grok 4 Fast — ultra barato com 2M contexto
    "or-grok-4-fast": LLMModel(
        id="or-grok-4-fast",
        provider="openrouter",
        model_name="x-ai/grok-4-fast",
        tier=ModelTier.ECONOMY,
        context_window=2_000_000,
        max_output=8_192,
        cost_input=0.20,
        cost_output=0.50,
        supports_cache=False,
        supports_vision=False,
        description="Grok 4 Fast — 2M contexto a $0.20/M, ultra barato"
    ),

    # ---------------------------- DEEPSEEK ----------------------------------
    "deepseek-v3": LLMModel(
        id="deepseek-v3",
        provider="deepseek",
        model_name="deepseek-chat",
        tier=ModelTier.STANDARD,
        context_window=64_000,
        max_output=8_192,
        cost_input=0.27,
        cost_output=1.10,
        supports_cache=True,
        supports_vision=False,
        description="DeepSeek V3 — excelente em código, muito barato"
    ),

    # ---------------------------- Z.AI (GLM / Zhipu) ------------------------
    # GLM-5.1 é o flagship atual (disponível nos planos Pro/Max do Coding Plan)
    "glm-5.1": LLMModel(
        id="glm-5.1",
        provider="zai",
        model_name="glm-5.1",
        tier=ModelTier.PREMIUM,
        context_window=200_000,
        max_output=16_384,
        cost_input=1.00,
        cost_output=3.50,
        supports_cache=True,
        supports_vision=False,
        description="GLM-5.1 — flagship da Z.ai, ótimo em código e agentes"
    ),
    # GLM-4.7 — excelente custo-benefício, 73.8% SWE-bench
    "glm-4.7": LLMModel(
        id="glm-4.7",
        provider="zai",
        model_name="glm-4.7",
        tier=ModelTier.STANDARD,
        context_window=202_752,
        max_output=8_192,
        cost_input=0.38,
        cost_output=1.74,
        supports_cache=True,
        supports_vision=False,
        description="GLM-4.7 — excelente em código, ~3x mais barato que Sonnet"
    ),
    # GLM-4.6 — versão anterior ainda forte e barata
    "glm-4.6": LLMModel(
        id="glm-4.6",
        provider="zai",
        model_name="glm-4.6",
        tier=ModelTier.STANDARD,
        context_window=204_800,
        max_output=8_192,
        cost_input=0.39,
        cost_output=1.74,
        supports_cache=True,
        supports_vision=False,
        description="GLM-4.6 — alternativa barata e capaz para tarefas médias"
    ),
    # GLM-4.7-Flash — GRÁTIS! Ideal para tarefas triviais e simples
    "glm-4.7-flash": LLMModel(
        id="glm-4.7-flash",
        provider="zai",
        model_name="glm-4.7-flash",
        tier=ModelTier.ECONOMY,
        context_window=203_000,
        max_output=8_192,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="GLM-4.7 Flash — GRÁTIS! Ótimo para tarefas leves e formatação"
    ),
    # GLM-4.5-Flash — GRÁTIS! Modelo leve de propósito geral
    "glm-4.5-flash": LLMModel(
        id="glm-4.5-flash",
        provider="zai",
        model_name="glm-4.5-flash",
        tier=ModelTier.ECONOMY,
        context_window=128_000,
        max_output=4_096,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="GLM-4.5 Flash — GRÁTIS! Modelo leve de propósito geral"
    ),
    # GLM-4.6V — versão com visão
    "glm-4.6v": LLMModel(
        id="glm-4.6v",
        provider="zai",
        model_name="glm-4.6v",
        tier=ModelTier.STANDARD,
        context_window=128_000,
        max_output=4_096,
        cost_input=0.30,
        cost_output=0.90,
        supports_cache=False,
        supports_vision=True,
        description="GLM-4.6V — versão multimodal (aceita imagens)"
    ),

    # ---------------------------- LOCAL (OLLAMA) ----------------------------
    "qwen-coder-local": LLMModel(
        id="qwen-coder-local",
        provider="ollama",
        model_name="qwen2.5-coder:14b",
        tier=ModelTier.LOCAL,
        context_window=32_000,
        max_output=4_096,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="Qwen 2.5 Coder 14B — local, grátis, bom para código rotineiro"
    ),
    "llama-local": LLMModel(
        id="llama-local",
        provider="ollama",
        model_name="llama3.2:8b",
        tier=ModelTier.LOCAL,
        context_window=128_000,
        max_output=4_096,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="Llama 3.2 8B — local, grátis, propósito geral"
    ),
    # === Bigmodel / Z.AI ===
    "bigmodel-glm-4.5-air": LLMModel(
        id="bigmodel-glm-4.5-air",
        provider="bigmodel",
        model_name="glm-4.5-air",
        tier=ModelTier.ECONOMY,
        context_window=131_072,
        max_output=4_096,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="GLM 4.5 Air via Bigmodel",
    ),
    "zai-glm-5.1": LLMModel(
        id="zai-glm-5.1",
        provider="zai",
        model_name="glm-5.1",
        tier=ModelTier.STANDARD,
        context_window=202_800,
        max_output=4_096,
        cost_input=0.0,
        cost_output=0.0,
        supports_cache=False,
        supports_vision=False,
        description="GLM-5.1 via Z.AI Coding Plan",
    ),
}


# ==========================================================================
# REGRAS DE ROTEAMENTO
# ==========================================================================

# Qual modelo usar para cada nível de complexidade (ordem = preferência).
# O roteador tenta o primeiro, se falhar/indisponível, passa para o próximo.
#
# ESTRATÉGIA DE ECONOMIA:
# - TRIVIAL:  grátis primeiro (Z.ai Flash, OpenRouter Free, Groq 8B)
# - SIMPLE:   grátis ou quase (OpenRouter, Z.ai Flash, Gemini Flash)
# - MEDIUM:   excelente custo-benefício (MiniMax, GLM-4.7, DeepSeek)
# - COMPLEX:  modelos fortes mas sem gastar muito (Sonnet, Qwen Max, Kimi)
# - CRITICAL: premium quando vale (Claude Opus, GPT-5)

# ESTRATÉGIA DE FALLBACK:
# - Cada nível distribui entre providers diferentes (nunca 2 do mesmo seguidos)
# - Se um cai, o próximo assume automaticamente
# - Providers ativos: zai (GLM-5.1), bigmodel (GLM-4.5-air), groq (Llama/Qwen),
#   openrouter (gateway 300+ modelos)
# - Ordem: grátis → barato → robusto → gateway

# ESTRATÉGIA: 100% modelos gratuitos, diversificados por provider
# Se um cai, o próximo assume. Sem custo.
# Prioridade: bigmodel (rápido) → groq (estável) → z.ai flash (free) → openrouter (variedade)
# NOTA: modelos free do OpenRouter têm rate limit frequente — sempre ter groq/bigmodel antes

ROUTING_RULES = {
    TaskComplexity.TRIVIAL: [
        "bigmodel-glm-4.5-air",      # free — respostas rápidas, baixa complexidade
        "glm-4.5-flash",              # free (z.ai flash)
        "groq-llama-3.1-8b",          # quase-free — ultra rápido
    ],
    TaskComplexity.SIMPLE: [
        "zai-glm-5.1",                # free (z.ai coding plan) — capaz, 200k ctx
        "glm-4.7-flash",              # free (z.ai) — bom custo-benefício
        "groq-llama-3.3-70b",         # quase-free (groq)
        "or-llama-3.3-70b-free",      # free (openrouter) — backup
    ],
    TaskComplexity.MEDIUM: [
        "zai-glm-5.1",                # free (z.ai) — orquestração, raciocínio
        "groq-kimi-k2",               # pago leve (groq) — 16k output, capaz
        "groq-qwen3-32b",             # quase-free (groq)
        "glm-4.7-flash",              # free (z.ai)
        "or-grok-4-fast",             # pago (openrouter) — backup robusto
    ],
    TaskComplexity.COMPLEX: [
        "zai-glm-5.1",                # free (z.ai) — primário para complexos
        "groq-kimi-k2",               # pago leve — 16k output, bom raciocínio
        "groq-gpt-oss-120b",          # quase-free — modelo grande, 131k ctx
        "groq-qwen3-32b",             # quase-free — backup
        "or-grok-4-fast",             # pago (openrouter) — último recurso
    ],
    TaskComplexity.CRITICAL: [
        "zai-glm-5.1",                # free (z.ai) — melhor disponível sem Anthropic
        "groq-kimi-k2",               # pago leve — raciocínio profundo
        "groq-gpt-oss-120b",          # quase-free — 120B params
        "or-grok-4-fast",             # pago (openrouter) — fallback premium
    ],
}

# Modelo usado para o próprio classificador de complexidade (precisa ser barato)
CLASSIFIER_MODEL = "gemini-flash-lite"

# Modelo usado para gerar embeddings de memória
EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI, barato e bom


# ==========================================================================
# CONFIGURAÇÕES DE MEMÓRIA
# ==========================================================================

@dataclass
class MemoryConfig:
    """Parâmetros do sistema de memória hierárquica."""

    # Camada QUENTE (contexto imediato, em RAM)
    hot_max_messages: int = 20          # Últimas 20 mensagens ficam em RAM
    hot_max_tokens: int = 8_000         # Ou no máximo 8k tokens

    # Camada MORNA (SQLite, acesso rápido)
    warm_max_days: int = 7              # Últimos 7 dias ficam "mornos"
    warm_max_entries: int = 500         # Ou 500 entradas no máximo

    # Camada FRIA (vault com embeddings, busca semântica)
    cold_max_days: int = 90             # Dados entre 7 e 90 dias
    cold_chunk_size: int = 500          # Tamanho dos pedaços para embedding

    # Camada ARQUIVO (comprimido, raramente acessado)
    archive_after_days: int = 90        # +90 dias vai para arquivo

    # Estratégia de compressão
    summarize_threshold_tokens: int = 4000  # Conversas > 4k tokens são resumidas
    summary_ratio: float = 0.2              # Resumo fica com 20% do original


MEMORY_CONFIG = MemoryConfig()


# ==========================================================================
# CHAVES DE API (lidas do .env)
# ==========================================================================

@dataclass
class APIKeys:
    """Chaves de API carregadas do arquivo .env."""
    anthropic: Optional[str] = None
    openai: Optional[str] = None
    google: Optional[str] = None
    deepseek: Optional[str] = None
    zai: Optional[str] = None
    bigmodel: Optional[str] = None      # open.bigmodel.cn (GLM free tier)
    groq: Optional[str] = None
    moonshot: Optional[str] = None       # Kimi
    minimax: Optional[str] = None
    alibaba: Optional[str] = None        # Qwen via DashScope
    openrouter: Optional[str] = None     # Gateway para 300+ modelos
    ollama_host: str = "http://localhost:11434"

    @classmethod
    def from_env(cls) -> "APIKeys":
        """Carrega chaves do ambiente."""
        return cls(
            anthropic=os.getenv("ANTHROPIC_API_KEY"),
            openai=os.getenv("OPENAI_API_KEY"),
            google=os.getenv("GOOGLE_API_KEY"),
            deepseek=os.getenv("DEEPSEEK_API_KEY"),
            zai=os.getenv("ZAI_API_KEY"),
            bigmodel=os.getenv("BIGMODEL_API_KEY"),
            groq=os.getenv("GROQ_API_KEY"),
            moonshot=os.getenv("MOONSHOT_API_KEY"),
            minimax=os.getenv("MINIMAX_API_KEY"),
            alibaba=os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY"),
            openrouter=os.getenv("OPENROUTER_API_KEY"),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        )

    def has_provider(self, provider: str) -> bool:
        """Verifica se temos chave para um provider específico."""
        mapping = {
            "anthropic": self.anthropic,
            "openai": self.openai,
            "google": self.google,
            "deepseek": self.deepseek,
            "zai": self.zai,
            "bigmodel": self.bigmodel,
            "groq": self.groq,
            "moonshot": self.moonshot,
            "minimax": self.minimax,
            "alibaba": self.alibaba,
            "openrouter": self.openrouter,
            "ollama": True,  # Ollama não precisa de chave
        }
        return bool(mapping.get(provider))


# ==========================================================================
# CONFIGURAÇÕES GERAIS
# ==========================================================================

@dataclass
class AppConfig:
    """Configuração geral do ClawVault."""
    app_name: str = "ClawVault"
    version: str = "0.1.0"
    language: str = "pt-BR"
    debug: bool = False

    # Modelo padrão se o roteador falhar em classificar
    default_model: str = "claude-sonnet-4-6"

    # Permitir fallback para modelos locais quando a API falhar?
    allow_local_fallback: bool = True

    # Orçamento mensal (em USD) — se exceder, só usa modelos baratos/locais
    monthly_budget_usd: float = 50.0

    # Habilitar cache de prompts automaticamente?
    enable_prompt_cache: bool = True

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            debug=os.getenv("DEBUG", "false").lower() == "true",
            default_model=os.getenv("DEFAULT_MODEL", "claude-sonnet-4-6"),
            allow_local_fallback=os.getenv("ALLOW_LOCAL_FALLBACK", "true").lower() == "true",
            monthly_budget_usd=float(os.getenv("MONTHLY_BUDGET_USD", "50.0")),
        )


# Instâncias globais
API_KEYS = APIKeys.from_env()
APP_CONFIG = AppConfig.from_env()
