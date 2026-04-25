"""
ClawVault - Roteador Inteligente de LLMs
=========================================

Este módulo é o coração do sistema de economia de tokens. Ele:

1. Recebe um prompt do usuário
2. Classifica a complexidade da tarefa
3. Escolhe o modelo mais adequado (mais barato que atende)
4. Faz a chamada (com fallback automático se falhar)
5. Registra uso e custo
6. Retorna a resposta padronizada

Todos os providers (Anthropic, OpenAI, Google, DeepSeek, Ollama)
retornam no mesmo formato padronizado.
"""

import time
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

from backend.core.config import (
    TaskComplexity,
    LLMModel,
    MODELS_CATALOG,
    ROUTING_RULES,
    API_KEYS,
    APP_CONFIG,
)
from backend.core.database import record_usage, get_monthly_spend
from backend.llm.classifier import classifier


# ==========================================================================
# RESPOSTA PADRONIZADA
# ==========================================================================

@dataclass
class LLMResponse:
    """Resposta unificada de qualquer provider."""
    content: str
    model_id: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    complexity: Optional[TaskComplexity] = None
    fallback_used: bool = False
    cached_response: bool = False
    error: Optional[str] = None
    raw_response: Optional[Any] = None
    # Métricas de compressão (se ativada)
    compression_saved_tokens: int = 0
    compression_level_used: Optional[str] = None


@dataclass
class LLMRequest:
    """Requisição unificada."""
    prompt: str
    system: Optional[str] = None
    messages: Optional[list[dict]] = None  # Histórico de mensagens
    complexity_hint: Optional[TaskComplexity] = None  # Forçar um nível
    model_override: Optional[str] = None  # Forçar um modelo específico
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    use_cache: bool = True
    conversation_id: Optional[int] = None
    # Compressão de prompt (economia de tokens)
    compress: bool = False                # Ligar compressão automática?
    compression_level: Optional[str] = None  # "soft", "balanced", "aggressive"
    # Modo M2M (comunicação entre agentes, sem prosa)
    m2m_mode: bool = False


# ==========================================================================
# ADAPTADORES POR PROVIDER
# ==========================================================================

class AnthropicAdapter:
    """Adaptador para a API da Anthropic (Claude)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                raise RuntimeError(
                    "Biblioteca 'anthropic' não instalada. "
                    "Rode: pip install anthropic"
                )
        return self._client

    def _split_system_for_caching(self, system: str) -> list:
        """
        Divide o system prompt em até 3 breakpoints cacheáveis com TTLs apropriados.

        Estratégia (do mais estável → mais dinâmico):
          1. Base (~tudo até a primeira quebra dupla) — TTL 1h
          2. Agente (entre primeira e segunda quebra) — TTL 1h
          3. Memória/contexto (resto) — TTL 5min (ephemeral default)
        """
        if not system or len(system) < 1024:
            return [{
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }]

        chunks = [c.strip() for c in system.split("\n\n", 2) if c.strip()]

        if len(chunks) == 1:
            return [{
                "type": "text",
                "text": chunks[0],
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }]

        if len(chunks) == 2:
            return [
                {"type": "text", "text": chunks[0],
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}},
                {"type": "text", "text": chunks[1],
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}},
            ]

        return [
            {"type": "text", "text": chunks[0],
             "cache_control": {"type": "ephemeral", "ttl": "1h"}},
            {"type": "text", "text": chunks[1],
             "cache_control": {"type": "ephemeral", "ttl": "1h"}},
            {"type": "text", "text": "\n\n".join(chunks[2:]),
             "cache_control": {"type": "ephemeral"}},
        ]

    def call(self, model: LLMModel, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        start = time.time()

        # Monta mensagens
        messages = request.messages or []
        if request.prompt and not messages:
            messages = [{"role": "user", "content": request.prompt}]
        elif request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        # Cache de sistema com múltiplos breakpoints (P8 — otimização)
        # A Anthropic permite até 4 breakpoints de cache_control por requisição.
        # Estratégia: cachear o que é estável (system base + agente) com TTL 1h,
        # e o que muda mais (memória) com TTL 5min (ephemeral default).
        system_param = request.system
        if model.supports_cache and system_param and APP_CONFIG.enable_prompt_cache:
            # Detecta separadores conhecidos no system prompt
            # (vault.py monta como: BASE + "\n\n" + agent_context)
            parts = self._split_system_for_caching(system_param)
            system_param = parts

        # Cache de mensagens longas (P8): se temos histórico extenso,
        # marca a penúltima mensagem como cache breakpoint.
        if (model.supports_cache and APP_CONFIG.enable_prompt_cache
                and len(messages) >= 4):
            history_text = "".join(
                m.get("content", "") if isinstance(m.get("content"), str)
                else "" for m in messages[:-1]
            )
            if len(history_text) >= 4096:  # ~1024 tokens
                target_idx = len(messages) - 2
                msg = messages[target_idx]
                if isinstance(msg.get("content"), str):
                    messages[target_idx] = {
                        "role": msg["role"],
                        "content": [{
                            "type": "text",
                            "text": msg["content"],
                            "cache_control": {"type": "ephemeral"},
                        }]
                    }

        kwargs = {
            "model": model.model_name,
            "max_tokens": request.max_tokens or model.max_output,
            "messages": messages,
            "temperature": request.temperature,
        }
        if system_param:
            kwargs["system"] = system_param

        response = client.messages.create(**kwargs)

        duration_ms = int((time.time() - start) * 1000)
        content = response.content[0].text if response.content else ""

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cached_tokens = getattr(response.usage, "cache_read_input_tokens", 0)

        # Cálculo de custo (cache custa 10% do input normal)
        cost = (
            ((input_tokens - cached_tokens) * model.cost_input / 1_000_000)
            + (cached_tokens * model.cost_input * 0.1 / 1_000_000)
            + (output_tokens * model.cost_output / 1_000_000)
        )

        return LLMResponse(
            content=content,
            model_id=model.id,
            provider="anthropic",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
            raw_response=response,
        )


class OpenAIAdapter:
    """Adaptador para a API da OpenAI (GPT)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise RuntimeError(
                    "Biblioteca 'openai' não instalada. Rode: pip install openai"
                )
        return self._client

    def call(self, model: LLMModel, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        start = time.time()

        messages = request.messages or []
        if request.system and not any(m.get("role") == "system" for m in messages):
            messages = [{"role": "system", "content": request.system}] + messages
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        response = client.chat.completions.create(
            model=model.model_name,
            messages=messages,
            max_tokens=request.max_tokens or model.max_output,
            temperature=request.temperature,
        )

        duration_ms = int((time.time() - start) * 1000)
        content = response.choices[0].message.content or ""

        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cached_tokens = getattr(response.usage, "prompt_tokens_cached", 0) or 0

        cost = (
            ((input_tokens - cached_tokens) * model.cost_input / 1_000_000)
            + (cached_tokens * model.cost_input * 0.5 / 1_000_000)
            + (output_tokens * model.cost_output / 1_000_000)
        )

        return LLMResponse(
            content=content,
            model_id=model.id,
            provider="openai",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
            raw_response=response,
        )


class GoogleAdapter:
    """Adaptador para a API do Google (Gemini)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._configured = False

    def _configure(self):
        if not self._configured:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._genai = genai
                self._configured = True
            except ImportError:
                raise RuntimeError(
                    "Biblioteca 'google-generativeai' não instalada. "
                    "Rode: pip install google-generativeai"
                )

    def call(self, model: LLMModel, request: LLMRequest) -> LLMResponse:
        self._configure()
        start = time.time()

        gen_model = self._genai.GenerativeModel(
            model_name=model.model_name,
            system_instruction=request.system,
        )

        # Monta histórico (Gemini usa formato diferente)
        history = []
        for msg in (request.messages or []):
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})

        chat = gen_model.start_chat(history=history)
        response = chat.send_message(
            request.prompt,
            generation_config={
                "max_output_tokens": request.max_tokens or model.max_output,
                "temperature": request.temperature,
            },
        )

        duration_ms = int((time.time() - start) * 1000)

        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count

        cost = (
            (input_tokens * model.cost_input / 1_000_000)
            + (output_tokens * model.cost_output / 1_000_000)
        )

        return LLMResponse(
            content=response.text,
            model_id=model.id,
            provider="google",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
            raw_response=response,
        )


class DeepSeekAdapter:
    """Adaptador para a API da DeepSeek (compatível com OpenAI)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://api.deepseek.com/v1",
                )
            except ImportError:
                raise RuntimeError("Biblioteca 'openai' não instalada.")
        return self._client

    def call(self, model: LLMModel, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        start = time.time()

        messages = request.messages or []
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        response = client.chat.completions.create(
            model=model.model_name,
            messages=messages,
            max_tokens=request.max_tokens or model.max_output,
            temperature=request.temperature,
        )

        duration_ms = int((time.time() - start) * 1000)
        content = response.choices[0].message.content or ""

        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        cost = (
            (input_tokens * model.cost_input / 1_000_000)
            + (output_tokens * model.cost_output / 1_000_000)
        )

        return LLMResponse(
            content=content,
            model_id=model.id,
            provider="deepseek",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
            raw_response=response,
        )


class ZaiAdapter:
    """
    Adaptador para a API da Z.ai (modelos GLM / Zhipu AI).

    A API da Z.ai é compatível com o SDK da OpenAI — só muda a base_url.
    Endpoint: https://api.z.ai/api/paas/v4/
    Docs: https://docs.z.ai/guides/develop/openai/python

    Inclui modelos grátis (glm-4.7-flash e glm-4.5-flash) — o roteador
    usa eles primeiro para tarefas triviais, economizando MUITO token.
    """

    BASE_URL = "https://api.z.ai/api/coding/paas/v4"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.BASE_URL,
                )
            except ImportError:
                raise RuntimeError(
                    "Biblioteca 'openai' não instalada. Rode: pip install openai"
                )
        return self._client

    def call(self, model: LLMModel, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        start = time.time()

        messages = request.messages or []
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        try:
            response = client.chat.completions.create(
                model=model.model_name,
                messages=messages,
                max_tokens=request.max_tokens or model.max_output,
                temperature=request.temperature,
            )
        except Exception as e:
            # Z.ai pode ter rate limits ou modelos temporariamente indisponíveis.
            # Deixa a exceção subir para o roteador acionar o fallback.
            raise RuntimeError(f"Erro Z.ai ({model.id}): {e}")

        duration_ms = int((time.time() - start) * 1000)
        content = response.choices[0].message.content or ""

        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        # Custo: para modelos grátis (glm-4.7-flash / glm-4.5-flash) = 0
        cost = (
            (input_tokens * model.cost_input / 1_000_000)
            + (output_tokens * model.cost_output / 1_000_000)
        )

        return LLMResponse(
            content=content,
            model_id=model.id,
            provider="zai",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
            raw_response=response,
        )


# ==========================================================================
# ADAPTADOR GENÉRICO OPENAI-COMPATIBLE
# ==========================================================================

class OpenAICompatibleAdapter:
    """
    Adaptador genérico para APIs compatíveis com OpenAI.

    Usado por Groq, Moonshot (Kimi), MiniMax e Alibaba DashScope (Qwen) —
    todos seguem o mesmo formato de chamadas. Economiza muita duplicação.

    Cada provider só precisa informar:
    - base_url (endpoint da API)
    - provider_name (nome interno para logs)
    """

    def __init__(self, api_key: str, base_url: str, provider_name: str):
        self.api_key = api_key
        self.base_url = base_url
        self.provider_name = provider_name
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise RuntimeError(
                    "Biblioteca 'openai' não instalada. Rode: pip install openai"
                )
        return self._client

    def call(self, model: LLMModel, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        start = time.time()

        messages = request.messages or []
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        try:
            response = client.chat.completions.create(
                model=model.model_name,
                messages=messages,
                max_tokens=request.max_tokens or model.max_output,
                temperature=request.temperature,
            )
        except Exception as e:
            raise RuntimeError(f"Erro {self.provider_name} ({model.id}): {e}")

        duration_ms = int((time.time() - start) * 1000)
        content = response.choices[0].message.content or ""

        # Alguns providers retornam o usage em formato um pouco diferente.
        # Tentamos os campos padrão e caímos em 0 se não encontrar.
        usage = response.usage
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        cached_tokens = (
            getattr(usage, "prompt_tokens_cached", None)
            or getattr(usage, "cached_tokens", None)
            or 0
        )

        cost = (
            (input_tokens * model.cost_input / 1_000_000)
            + (output_tokens * model.cost_output / 1_000_000)
        )

        return LLMResponse(
            content=content,
            model_id=model.id,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
            raw_response=response,
        )


# ---------- Instâncias especializadas (wrappers curtos) -------------------

class GroqAdapter(OpenAICompatibleAdapter):
    """
    Adaptador para Groq (inferência ultra rápida com LPU).

    Hospeda apenas modelos open-source (Llama, Qwen, gpt-oss, Kimi, MiniMax).
    Vantagens: 300-1000 tokens/segundo, free tier generoso sem cartão.
    Docs: https://console.groq.com/docs
    """
    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str):
        super().__init__(api_key, self.BASE_URL, "groq")


class MoonshotAdapter(OpenAICompatibleAdapter):
    """
    Adaptador para a Moonshot AI (criadora do Kimi).

    Modelos: kimi-k2, kimi-k2.5, kimi-k2.6.
    Docs: https://platform.moonshot.ai/docs
    """
    # Endpoint internacional (tem também um endpoint .cn para China)
    BASE_URL = "https://api.moonshot.ai/v1"

    def __init__(self, api_key: str):
        super().__init__(api_key, self.BASE_URL, "moonshot")


class MiniMaxAdapter(OpenAICompatibleAdapter):
    """
    Adaptador para a MiniMax.

    Modelos: MiniMax-M2.5, M2.7, Lightning.
    Docs: https://www.minimax.io/platform/document/ChatCompletion
    """
    BASE_URL = "https://api.minimax.io/v1"

    def __init__(self, api_key: str):
        super().__init__(api_key, self.BASE_URL, "minimax")


class AlibabaAdapter(OpenAICompatibleAdapter):
    """
    Adaptador para a Alibaba Cloud (DashScope — modelos Qwen).

    Modelos: qwen3-turbo, qwen3-coder, qwen3.6-plus, qwen3.6-max-preview, etc.
    Endpoint internacional (Singapore). Para China use: dashscope.aliyuncs.com.
    Docs: https://www.alibabacloud.com/help/en/model-studio
    """
    BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    def __init__(self, api_key: str):
        super().__init__(api_key, self.BASE_URL, "alibaba")


class OpenRouterAdapter:
    """
    Adaptador para o OpenRouter — gateway que dá acesso a 300+ modelos
    com uma única chave de API.

    Endpoint: https://openrouter.ai/api/v1 (OpenAI-compatible)
    Docs: https://openrouter.ai/docs

    Diferenciais deste adaptador:
    1. Headers extras (HTTP-Referer, X-Title) recomendados pelo OpenRouter
       para aparecer nos rankings e ter melhor rate-limit
    2. Aceita modelos no formato "provider/modelo" (ex: anthropic/claude-opus)
    3. Modelos grátis têm sufixo ":free" (ex: meta-llama/llama-3.3-70b:free)
    4. Quando usado diretamente via --model, o nome pode vir no formato
       "openrouter/<modelo>" e é automaticamente convertido
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, app_name: str = "ClawVault"):
        self.api_key = api_key
        self.app_name = app_name
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.BASE_URL,
                    # Headers recomendados pelo OpenRouter para tracking e
                    # melhor prioridade em rate limits
                    default_headers={
                        "HTTP-Referer": "https://github.com/clawvault",
                        "X-Title": self.app_name,
                    },
                )
            except ImportError:
                raise RuntimeError(
                    "Biblioteca 'openai' não instalada. Rode: pip install openai"
                )
        return self._client

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        """
        Converte IDs internos para o formato que o OpenRouter espera.
        Aceita tanto 'openrouter/anthropic/claude-opus' quanto
        'anthropic/claude-opus' direto.
        """
        if name.startswith("openrouter/"):
            return name[len("openrouter/"):]
        return name

    def call(self, model: LLMModel, request: LLMRequest) -> LLMResponse:
        client = self._get_client()
        start = time.time()

        messages = request.messages or []
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        model_name = self._normalize_model_name(model.model_name)

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=request.max_tokens or model.max_output,
                temperature=request.temperature,
            )
        except Exception as e:
            raise RuntimeError(f"Erro OpenRouter ({model.id} → {model_name}): {e}")

        duration_ms = int((time.time() - start) * 1000)
        content = response.choices[0].message.content or ""

        usage = response.usage
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0

        cost = (
            (input_tokens * model.cost_input / 1_000_000)
            + (output_tokens * model.cost_output / 1_000_000)
        )

        return LLMResponse(
            content=content,
            model_id=model.id,
            provider="openrouter",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
            raw_response=response,
        )


class OllamaAdapter:
    """Adaptador para Ollama (modelos locais, grátis)."""

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host

    def call(self, model: LLMModel, request: LLMRequest) -> LLMResponse:
        try:
            import requests
        except ImportError:
            raise RuntimeError("Biblioteca 'requests' não instalada.")

        start = time.time()

        messages = request.messages or []
        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        response = requests.post(
            f"{self.host}/api/chat",
            json={
                "model": model.model_name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens or model.max_output,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        duration_ms = int((time.time() - start) * 1000)
        content = data.get("message", {}).get("content", "")

        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        return LLMResponse(
            content=content,
            model_id=model.id,
            provider="ollama",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=0.0,  # Local = grátis
            duration_ms=duration_ms,
            raw_response=data,
        )


# ==========================================================================
# ROTEADOR PRINCIPAL
# ==========================================================================

class LLMRouter:
    """
    Roteador inteligente que escolhe o melhor modelo para cada tarefa.

    Fluxo:
    1. Classifica complexidade (se não foi fornecida)
    2. Pega lista de modelos recomendados para essa complexidade
    3. Filtra apenas os que têm API key configurada
    4. Verifica orçamento mensal (se exceder, força modelos baratos)
    5. Tenta o primeiro modelo; se falhar, tenta os próximos
    6. Registra uso e retorna resposta padronizada
    """

    def __init__(self):
        self._adapters: dict[str, Any] = {}

    def _get_adapter(self, provider: str):
        """Retorna adaptador para o provider (lazy init)."""
        if provider in self._adapters:
            return self._adapters[provider]

        if provider == "anthropic" and API_KEYS.anthropic:
            self._adapters[provider] = AnthropicAdapter(API_KEYS.anthropic)
        elif provider == "openai" and API_KEYS.openai:
            self._adapters[provider] = OpenAIAdapter(API_KEYS.openai)
        elif provider == "google" and API_KEYS.google:
            self._adapters[provider] = GoogleAdapter(API_KEYS.google)
        elif provider == "deepseek" and API_KEYS.deepseek:
            self._adapters[provider] = DeepSeekAdapter(API_KEYS.deepseek)
        elif provider == "zai" and API_KEYS.zai:
            self._adapters[provider] = ZaiAdapter(API_KEYS.zai)
        elif provider == "groq" and API_KEYS.groq:
            self._adapters[provider] = GroqAdapter(API_KEYS.groq)
        elif provider == "moonshot" and API_KEYS.moonshot:
            self._adapters[provider] = MoonshotAdapter(API_KEYS.moonshot)
        elif provider == "minimax" and API_KEYS.minimax:
            self._adapters[provider] = MiniMaxAdapter(API_KEYS.minimax)
        elif provider == "alibaba" and API_KEYS.alibaba:
            self._adapters[provider] = AlibabaAdapter(API_KEYS.alibaba)
        elif provider == "bigmodel" and os.getenv("BIGMODEL_API_KEY"):
            self._adapters[provider] = BigmodelAdapter(os.getenv("BIGMODEL_API_KEY"))
        elif provider == "openrouter" and API_KEYS.openrouter:
            self._adapters[provider] = OpenRouterAdapter(API_KEYS.openrouter)
        elif provider == "ollama":
            self._adapters[provider] = OllamaAdapter(API_KEYS.ollama_host)
        else:
            return None

        return self._adapters[provider]

    def _filter_available_models(self, model_ids: list[str]) -> list[LLMModel]:
        """Filtra apenas modelos que têm API key disponível."""
        available = []
        for model_id in model_ids:
            model = MODELS_CATALOG.get(model_id)
            if not model:
                continue
            if API_KEYS.has_provider(model.provider):
                available.append(model)
        return available

    def _check_budget(self) -> bool:
        """Retorna True se ainda tem orçamento, False se excedeu."""
        spend = get_monthly_spend()
        return spend["spent_usd"] < APP_CONFIG.monthly_budget_usd

    def route(self, request: LLMRequest) -> LLMResponse:
        """
        Roteia a requisição para o melhor modelo disponível.
        """
        # ============== FASE 0: COMPRESSÃO / M2M (opcional) ==============
        # Se o usuário pediu compressão ou M2M, transformamos o prompt
        # antes de qualquer outra coisa. Isso economiza tokens de input
        # e também afeta a classificação de complexidade.
        compression_saved = 0
        compression_level_str = None

        if request.m2m_mode:
            # Modo máquina: instrução de sistema M2M + prompt comprimido agressivo
            from backend.llm.compressor import PromptCompressor, CompressionLevel, M2MProtocol
            compressor_ = PromptCompressor()
            result = compressor_.compress(request.prompt, level=CompressionLevel.AGGRESSIVE)
            request.prompt = result.compressed
            compression_saved = result.saved_tokens_est
            compression_level_str = "m2m"
            # Prepend do system prompt M2M (se não houver um customizado)
            m2m_sys = M2MProtocol.system_prompt_m2m()
            request.system = f"{m2m_sys}\n{request.system}" if request.system else m2m_sys

        elif request.compress:
            # Compressão normal (humano→LLM)
            from backend.llm.compressor import PromptCompressor, CompressionLevel
            level_map = {
                "soft": CompressionLevel.SOFT,
                "balanced": CompressionLevel.BALANCED,
                "aggressive": CompressionLevel.AGGRESSIVE,
            }
            level = level_map.get(
                (request.compression_level or "balanced").lower(),
                CompressionLevel.BALANCED,
            )
            compressor_ = PromptCompressor()
            result = compressor_.compress(request.prompt, level=level)
            request.prompt = result.compressed
            compression_saved = result.saved_tokens_est
            compression_level_str = level.name.lower()

        # ============== FASE 1: CLASSIFICAR COMPLEXIDADE ==============
        complexity = request.complexity_hint
        if complexity is None:
            complexity = classifier.classify(request.prompt)

        # 2. Modelo forçado?
        if request.model_override:
            override = request.model_override
            model = MODELS_CATALOG.get(override)

            # Caso especial: modelo ad-hoc do OpenRouter
            # Permite usar qualquer modelo passando "openrouter/<provider>/<nome>"
            # sem precisar catalogar. Ex: "openrouter/anthropic/claude-opus-4.5"
            if model is None and override.startswith("openrouter/") and API_KEYS.openrouter:
                model = LLMModel(
                    id=override,
                    provider="openrouter",
                    model_name=override[len("openrouter/"):],
                    tier=ModelTier.STANDARD,
                    context_window=128_000,
                    max_output=8_192,
                    cost_input=0.0,   # custo desconhecido — OpenRouter cobra pelo real
                    cost_output=0.0,
                    supports_cache=False,
                    supports_vision=False,
                    description=f"Modelo ad-hoc via OpenRouter: {override}",
                )

            if model:
                candidates = [model]
            else:
                return LLMResponse(
                    content="",
                    model_id=override,
                    provider="unknown",
                    error=(
                        f"Modelo '{override}' não encontrado no catálogo. "
                        f"Dica: para usar qualquer modelo do OpenRouter, "
                        f"prefixe com 'openrouter/' (ex: openrouter/anthropic/claude-opus-4.5)"
                    ),
                )
        else:
            # 3. Lista de candidatos baseada em complexidade
            model_ids = ROUTING_RULES.get(complexity, [APP_CONFIG.default_model])
            candidates = self._filter_available_models(model_ids)

        if not candidates:
            return LLMResponse(
                content="",
                model_id="none",
                provider="none",
                error=(
                    "Nenhum modelo disponível. "
                    "Verifique suas chaves de API no arquivo .env"
                ),
            )

        # 4. Verifica orçamento — se excedeu, força modelos baratos/locais
        if not self._check_budget():
            budget_friendly = [
                m for m in candidates
                if m.cost_input == 0 or m.tier.value in ("local", "economy")
            ]
            if budget_friendly:
                candidates = budget_friendly

        # 5. Tenta os modelos em ordem (fallback automático)
        last_error = None
        fallback_used = False
        import logging
        logger = logging.getLogger("clawvault.router")

        for idx, model in enumerate(candidates):
            adapter = self._get_adapter(model.provider)
            if adapter is None:
                continue

            try:
                response = adapter.call(model, request)
                response.complexity = complexity
                response.fallback_used = fallback_used
                # Propaga métricas de compressão
                response.compression_saved_tokens = compression_saved
                response.compression_level_used = compression_level_str

                # Registra uso no banco
                record_usage(
                    model_id=model.id,
                    provider=model.provider,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cached_tokens=response.cached_tokens,
                    cost_usd=response.cost_usd,
                    operation="chat",
                    conversation_id=request.conversation_id,
                    success=True,
                )
                return response

            except Exception as e:
                last_error = str(e)
                fallback_used = True
                logger.warning(f"[Fallback] {model.id} ({model.provider}) falhou: {str(e)[:100]}")
                # Registra falha e tenta próximo
                record_usage(
                    model_id=model.id,
                    provider=model.provider,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    operation="chat",
                    conversation_id=request.conversation_id,
                    success=False,
                    error_message=str(e)[:500],
                )
                continue

        return LLMResponse(
            content="",
            model_id="none",
            provider="none",
            complexity=complexity,
            error=f"Todos os modelos falharam. Último erro: {last_error}",
        )


# Instância global
router = LLMRouter()

class BigmodelAdapter(OpenAICompatibleAdapter):
    """
    Adaptador para Bigmodel/Zhipu AI (open.bigmodel.cn).
    
    Usa créditos de boas-vindas + modelos free (glm-4.5-flash, glm-4.7-flash).
    Endpoint compatível com OpenAI SDK.
    """
    BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(self, api_key: str):
        super().__init__(api_key, self.BASE_URL, "bigmodel")
