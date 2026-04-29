"""
ClawVault - Classificador de Complexidade v2
=============================================

Estratégia em 3 camadas:
  1. Heurísticas rápidas (regex) — zero custo, resolve ~60% dos casos
  2. LLM fallback com modelo free (glm-4.5-flash) — resolve ~35%
  3. Histograma boost — ajusta para cima se contexto exige

Mantém interface compatível com TaskComplexity enum.
"""

import hashlib
import logging
import os
import re
import time
from collections import deque
from typing import Optional

from backend.core.config import TaskComplexity

logger = logging.getLogger(__name__)

# ==========================================================================
# HEURÍSTICAS RÁPIDAS (zero custo)
# ==========================================================================

# Saudações → TRIVIAL (não precisa de LLM)
GREETING_RE = re.compile(
    r"^(oi|olá|ola|hey|hello|hi|eai|e ai|fala|beleza|blz|"
    r"tudo bem|td bem|bom dia|boa tarde|boa noite|"
    r"valeu|obrigad[oa]|tchau|bye|até)[\s!.,?;~]*$",
    re.IGNORECASE,
)

# Comandos curtos / lookup simples → TRIVIAL
TRIVIAL_PATTERNS = [
    re.compile(r"^(sim|não|nao|ok|certo|claro|perfeito|exato|isso|correto)[\s!.,?]*$", re.I),
    re.compile(r"^(obrigad[oa]|valeu|thanks|thx)[\s!.,?]*$", re.I),
    re.compile(r"^(bom dia|boa tarde|boa noite)[\s!.,?]*$", re.I),
]

# Keywords que determinam complexidade SEM precisar de LLM
CRITICAL_KW = [
    "decisão de negócio", "business decision", "investimento", "investment",
    "contrato", "contract", "análise financeira", "analise financeira",
    "risco legal", "auditoria", "audit", "pitch deck",
    "código de produção", "production code", "deploy em produção",
    "decisão estratégica", "decisao estrategica", "arquitetura de",
    "projete a arquitetura", "design the architecture",
]

COMPLEX_KW = [
    "arquitetura", "architecture", "refatore", "refactor",
    "otimize", "optimize", "debug complexo", "analise profundamente",
    "estratégia", "strategy", "compare as opções",
    "vantagens e desvantagens", "prós e contras", "pros and cons",
    "explique detalhadamente", "passo a passo", "step by step",
    "microservices", "microsserviços", "monolito", "monolith",
    "escalabilidade", "scalability", "sistema de pagamento",
    "analise comparativa", "comparative analysis",
    "diferença entre", "compare",
    "explique a diferença", "analise as vantagens",
]

# Padrões de entidade (aumentam peso)
ENTITY_RE = [
    re.compile(r"\bR\$\s*[\d.,]+"),
    re.compile(r"\$[\d.,]+"),
    re.compile(r"\bUSD\s*[\d.,]+"),
    re.compile(r"\b(prazo|deadline|entreg[ae])\b", re.I),
    re.compile(r"\b(projeto|project|cliente|client)\b", re.I),
    re.compile(r"\b(servidor|server|api|database|banco de dados)\b", re.I),
    re.compile(r"\b(segurança|security|credencial|token|senha)\b", re.I),
    re.compile(r"\b(produção|deploy|release|versão\s+\d)\b", re.I),
]

CODE_RE = re.compile(r"```|def |class |function |import |require\(|from \w+ import")


def _count_entities(text: str) -> int:
    return sum(1 for p in ENTITY_RE if p.search(text))


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


# ==========================================================================
# CLASSIFICADOR
# ==========================================================================

class TaskClassifier:
    """
    Classifica tarefas em 5 níveis.
    
    Fluxo:
      1. Heurísticas regex (instantâneo, zero custo)
      2. Se ambíguo → LLM barato (glm-4.5-flash, ~50 tokens, custo ~$0)
      3. Histograma boost ajusta para cima se contexto é consistentemente complexo
    """

    def __init__(self, use_llm_fallback: bool = True):
        self.use_llm_fallback = use_llm_fallback
        self._history: deque = deque(maxlen=5)
        # Cache de classificações (hash → resultado) — evita LLM pra mesma msg
        self._cache: dict[str, TaskComplexity] = {}
        self._cache_max = 200

    def classify(
        self,
        prompt: str,
        context: Optional[str] = None,
        message_count: int = 0,
    ) -> TaskComplexity:
        """Classify a prompt into a TaskComplexity level.

    Args:
        prompt: The user's message.
        context: Optional additional context (vault content, etc.).
        message_count: Number of previous messages in conversation.

    Returns:
        TaskComplexity: Classified complexity level.
    """
        full_text = prompt + " " + (context or "")
        prompt_stripped = prompt.strip()

        # === CAMADA 1: Heurísticas rápidas ===

        # R0: Saudações → TRIVIAL
        if GREETING_RE.match(prompt_stripped):
            return self._record(TaskComplexity.TRIVIAL)

        # R0b: Respostas curtas / afirmativas → TRIVIAL
        for pat in TRIVIAL_PATTERNS:
            if pat.match(prompt_stripped):
                return self._record(TaskComplexity.TRIVIAL)

        # R1: Keywords críticas
        text_lower = full_text.lower()
        if any(kw in text_lower for kw in CRITICAL_KW):
            return self._record(TaskComplexity.CRITICAL)

        # R2: Keywords complexas
        if any(kw in text_lower for kw in COMPLEX_KW):
            result = TaskComplexity.COMPLEX
            if self._history_boost():
                result = TaskComplexity.CRITICAL
            return self._record(result)

        # R3: Muitas entidades = pelo menos COMPLEX
        entity_count = _count_entities(full_text)
        if entity_count >= 3:
            return self._record(TaskComplexity.COMPLEX)

        # R4: Código = pelo menos MEDIUM
        if CODE_RE.search(prompt):
            return self._record(TaskComplexity.MEDIUM)

        # R5: Prompt muito curto (< 20 tokens) sem keywords especiais → SIMPLE
        prompt_tokens = _estimate_tokens(prompt)
        if prompt_tokens < 20:
            return self._record(TaskComplexity.SIMPLE)

        # R6: Entidades presentes = pelo menos MEDIUM
        if entity_count >= 1:
            result = TaskComplexity.MEDIUM
            if self._history_boost():
                result = TaskComplexity.COMPLEX
            return self._record(result)

        # R7: Prompt muito longo (> 500 tokens)
        if prompt_tokens > 500:
            result = TaskComplexity.MEDIUM
            if self._history_boost():
                result = TaskComplexity.COMPLEX
            return self._record(result)

        # === CAMADA 2: LLM fallback ===
        if self.use_llm_fallback:
            llm_result = self._llm_classify(prompt)
            if llm_result is not None:
                # Histograma boost pode aumentar
                if self._history_boost() and llm_result.value < TaskComplexity.COMPLEX.value:
                    llm_result = TaskComplexity(llm_result.value + 1)
                return self._record(llm_result)

        # Fallback seguro: MEDIUM
        return self._record(TaskComplexity.MEDIUM)

    def _llm_classify(self, prompt: str) -> Optional[TaskComplexity]:
        """Classify using a free LLM model (glm-4.5-flash).

    Uses minimal prompt (~50 tokens input), expects 1 token output.

    Args:
        prompt: User message to classify.

    Returns:
        TaskComplexity or None if classification fails.
    """
        # Check cache
        cache_key = hashlib.md5(prompt[:500].encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            import requests
            
            classification_prompt = (
                "Classifique a complexidade desta mensagem de 1 (trivial) a 5 (crítico).\n"
                "1=trivial/saudação, 2=simples/lookup, 3=médio/análise, "
                "4=complexo/arquitetura, 5=crítico/decisão de negócio.\n"
                "Responda APENAS com um número.\n\n"
                f"Mensagem: {prompt[:300]}"
            )

            # Tenta Z.AI primeiro (free coding plan)
            result = self._call_zai(classification_prompt)
            if result is None:
                # Fallback: Bigmodel
                result = self._call_bigmodel(classification_prompt)
            
            if result is not None:
                self._add_to_cache(cache_key, result)
                return result

        except Exception as e:
            logger.debug(f"[Classifier] LLM fallback falhou: {e}")

        return None

    def _call_zai(self, prompt: str) -> Optional[TaskComplexity]:
        """Chama Z.AI API para classificação rápida."""
        try:
            import requests
            api_key = os.environ.get("ZAI_API_KEY", "")
            if not api_key:
                return None
            
            resp = requests.post(
                "https://api.z.ai/api/coding/paas/v4/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "glm-4.5-flash",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 5,
                    "temperature": 0.0,
                },
                timeout=5,
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                match = re.search(r"[1-5]", text)
                if match:
                    return TaskComplexity(int(match.group()))
        except Exception:
            pass
        return None

    def _call_bigmodel(self, prompt: str) -> Optional[TaskComplexity]:
        """Chama Bigmodel API para classificação rápida."""
        try:
            import requests
            api_key = os.environ.get("BIGMODEL_API_KEY", "")
            if not api_key:
                return None
            
            resp = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "glm-4.5-flash",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 5,
                    "temperature": 0.0,
                },
                timeout=5,
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                match = re.search(r"[1-5]", text)
                if match:
                    return TaskComplexity(int(match.group()))
        except Exception:
            pass
        return None

    def _record(self, complexity: TaskComplexity) -> TaskComplexity:
        self._history.append(complexity.value)
        return complexity

    def _history_boost(self) -> bool:
        """True se últimas mensagens foram consistentemente complexas."""
        if len(self._history) < 3:
            return False
        return all(v >= TaskComplexity.MEDIUM.value for v in self._history)

    def _add_to_cache(self, key: str, result: TaskComplexity):
        """Adiciona ao cache com eviction."""
        if len(self._cache) >= self._cache_max:
            # Remove 20% mais antigo (approx FIFO)
            keys_to_remove = list(self._cache.keys())[:self._cache_max // 5]
            for k in keys_to_remove:
                del self._cache[k]
        self._cache[key] = result

    def classify_with_explanation(
        self,
        prompt: str,
        context: Optional[str] = None,
        message_count: int = 0,
    ) -> tuple:
        """Classify and return explanation string for debugging.

    Args:
        prompt: User message.
        context: Optional context.
        message_count: Previous message count.

    Returns:
        tuple: (TaskComplexity, explanation_string)
    """
        result = self.classify(prompt, context, message_count)
        
        prompt_stripped = prompt.strip()
        if GREETING_RE.match(prompt_stripped):
            return result, "Saudação detectada → TRIVIAL"
        
        text_lower = (prompt + " " + (context or "")).lower()
        if any(kw in text_lower for kw in CRITICAL_KW):
            return result, "Keywords críticas detectadas"
        if any(kw in text_lower for kw in COMPLEX_KW):
            return result, "Keywords complexas detectadas"
        
        entity_count = _count_entities(text_lower)
        if entity_count >= 3:
            return result, f"{entity_count} entidades detectadas → COMPLEX"
        if CODE_RE.search(prompt):
            return result, "Código detectado → MEDIUM+"
        
        return result, "Classificado via heurísticas/LLM fallback"


# Instância global
classifier = TaskClassifier()
