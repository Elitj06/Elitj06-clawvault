"""
ClawVault - Classificador de Complexidade (REESCRITO)
======================================================

Melhorias:
  1. Análise de entidade/projeto — detecta menções a projetos, valores, prazos
  2. Context window scoring — nº de mensagens na conversa, temas acumulados
  3. LLM fallback com modelo barato (prompt curto, 1-token response)
  4. Histograma de complexidade — se últimas 5 msgs foram MEDIUM+, aumentar nível
  5. Compatível com TaskComplexity enum existente
"""

import os
import re
from collections import deque
from typing import Optional

from backend.core.config import TaskComplexity


# ==========================================================================
# KEYWORDS
# ==========================================================================

TRIVIAL_KEYWORDS = [
    "liste", "lista", "list",
    "formate", "formatar", "format",
    "extraia", "extrair", "extract",
    "converta", "converter", "convert",
    "traduza palavra", "palavra em inglês", "palavra em português",
    "qual a capital", "qual o dia",
    "quantas letras", "quantos caracteres",
]

GREETING_PATTERNS = [
    r"^(oi|olá|ola|hey|hello|hi|eai|e ai|fala|beleza|blz|tudo bem|td bem|bom dia|boa tarde|boa noite)[\s!.,?]*$",
]

SIMPLE_KEYWORDS = [
    "resuma", "resumir", "summarize",
    "o que é", "o que significa",
    "explique rapidamente", "explain briefly",
    "traduza", "translate",
    "corrija gramática", "fix grammar",
    "qual a diferença entre",
]

COMPLEX_KEYWORDS = [
    "arquitetura", "architecture",
    "projete", "projetar", "design",
    "analise profundamente", "deep analysis",
    "refatore", "refactor",
    "debug", "depure",
    "otimize", "optimize",
    "estratégia", "strategy",
    "compare as opções", "compare options",
    "diferença entre", "compare",
    "explique detalhadamente", "passo a passo",
    "vantagens e desvantagens", "prós e contras",
]

CRITICAL_KEYWORDS = [
    "decisão de negócio", "business decision",
    "investimento", "investment",
    "investir", "invest",
    "contrato", "contract",
    "código de produção", "production code",
    "auditoria", "audit",
    "análise financeira", "analise financeira", "financial analysis",
    "risco legal", "legal risk",
    "pitch deck", "apresentação para investidor",
    "risco financeiro", "riscos financeiros",
    "decisão estratégica", "decisao estrategica",
]

# Entidades/projetos — menções que aumentam complexidade
ENTITY_PATTERNS = [
    r"\bR\$\s*[\d.,]+",             # valores em reais
    r"\$[\d.,]+",                   # valores em dólar
    r"\bUSD\s*[\d.,]+",             # USD
    r"\bprazo\b",                   # prazos
    r"\bdeadline\b",                # deadlines
    r"\bentreg[ae]\b.*\b\d",        # entregas com datas
    r"\bprojeto\b",                 # projetos
    r"\bproject\b",
    r"\bcliente\b",                 # clientes
    r"\bclient\b",
    r"\bequipe\b",                  # equipes
    r"\bteam\b",
    r"\bversão\s+\d",               # versões (v1, v2)
    r"\brelease\b",
    r"\bdeploy\b",
    r"\bprodução\b",
    r"\bserver\b|\bservidor\b",
    r"\bapi\b",
    r"\bdatabase\b|\bbanco de dados\b",
    r"\bsegurança\b|\bsecurity\b",
    r"\bcredencial\b|\btoken\b|\bsenha\b",
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _has_code_block(text: str) -> bool:
    return bool(re.search(r"```|def |class |function |import |require\(", text))


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _count_entities(text: str) -> int:
    """Conta menções a entidades/projetos/valores/prazos."""
    count = 0
    for pattern in ENTITY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            count += 1
    return count


# ==========================================================================
# CLASSIFICADOR
# ==========================================================================

class TaskClassifier:
    """
    Classifica tarefas em 5 níveis com análise contextual avançada.
    """

    def __init__(self, use_llm_fallback: bool = False):
        self.use_llm_fallback = use_llm_fallback
        # Histograma das últimas classificações
        self._history: deque = deque(maxlen=5)

    def classify(self, prompt: str, context: Optional[str] = None,
                 message_count: int = 0) -> TaskComplexity:
        full_text = prompt + " " + (context or "")

        # Regra 0: saudações → TRIVIAL
        prompt_stripped = prompt.strip().lower()
        for pattern in GREETING_PATTERNS:
            if re.match(pattern, prompt_stripped, re.IGNORECASE):
                self._record(TaskComplexity.TRIVIAL)
                return TaskComplexity.TRIVIAL

        # Regra 1: keywords críticas
        if _contains_any(full_text, CRITICAL_KEYWORDS):
            self._record(TaskComplexity.CRITICAL)
            return TaskComplexity.CRITICAL

        # Regra 2: keywords complexas
        if _contains_any(full_text, COMPLEX_KEYWORDS):
            result = TaskComplexity.COMPLEX
            # Histograma boost
            if self._history_boost():
                result = TaskComplexity.CRITICAL
            self._record(result)
            return result

        # Regra 3: análise de entidade/projeto
        entity_count = _count_entities(full_text)
        if entity_count >= 3:
            self._record(TaskComplexity.COMPLEX)
            return TaskComplexity.COMPLEX
        elif entity_count >= 1:
            # Entidades presentes = pelo menos MEDIUM
            pass  # continua avaliação, mas floor = MEDIUM

        # Regra 4: context window scoring
        prompt_tokens = _estimate_tokens(prompt)
        if message_count > 10:
            # Conversa longa com muitos temas → tende a complexo
            if prompt_tokens > 200:
                self._record(TaskComplexity.COMPLEX)
                return TaskComplexity.COMPLEX

        # Regra 5: prompt muito curto
        if prompt_tokens < 20:
            if _contains_any(prompt, TRIVIAL_KEYWORDS):
                self._record(TaskComplexity.TRIVIAL)
                return TaskComplexity.TRIVIAL
            result = TaskComplexity.SIMPLE
            self._record(result)
            return result

        # Regra 6: prompt muito longo
        if prompt_tokens > 500:
            if _has_code_block(prompt):
                self._record(TaskComplexity.COMPLEX)
                return TaskComplexity.COMPLEX
            result = TaskComplexity.MEDIUM
            if self._history_boost():
                result = TaskComplexity.COMPLEX
            self._record(result)
            return result

        # Regra 7: keywords simples
        if _contains_any(full_text, SIMPLE_KEYWORDS):
            self._record(TaskComplexity.SIMPLE)
            return TaskComplexity.SIMPLE

        # Regra 8: código = pelo menos MEDIUM
        if _has_code_block(prompt):
            self._record(TaskComplexity.MEDIUM)
            return TaskComplexity.MEDIUM

        # Regra 9: entidades = pelo menos MEDIUM
        if entity_count >= 1:
            result = TaskComplexity.MEDIUM
            if self._history_boost():
                result = TaskComplexity.COMPLEX
            self._record(result)
            return result

        # Regra 10: histograma boost no fallback
        if self._history_boost():
            self._record(TaskComplexity.MEDIUM)
            return TaskComplexity.MEDIUM

        # LLM fallback (opcional — se ativado e heurísticas não resolveram)
        if self.use_llm_fallback:
            try:
                result = self._llm_fallback(prompt)
                if result is not None:
                    self._record(result)
                    return result
            except Exception:
                pass

        # Fallback: MEDIUM
        self._record(TaskComplexity.MEDIUM)
        return TaskComplexity.MEDIUM

    def _record(self, complexity: TaskComplexity) -> None:
        self._history.append(complexity.value)

    def _history_boost(self) -> bool:
        """True se últimas 5 msgs foram MEDIUM+."""
        if len(self._history) < 3:
            return False
        return all(v >= TaskComplexity.MEDIUM.value for v in self._history)

    def _llm_fallback(self, prompt: str) -> Optional[TaskComplexity]:
        """
        Usa LLM barato (glm-4.5-air ou similar) pra classificar.
        Prompt curto, espera resposta de 1 token (número 1-5).
        """
        try:
            from backend.llm.router import router, LLMRequest
            response = router.route(LLMRequest(
                prompt=f"Classifique a complexidade desta pergunta de 1 (trivial) a 5 (crítica). Responda APENAS com um número.\n\nPergunta: {prompt[:500]}",
                complexity_hint=TaskComplexity.TRIVIAL,  # força modelo mais barato
                temperature=0.0,
                max_tokens=5,
            ))
            if response and response.content:
                text = response.content.strip()
                # Extrai número
                match = re.search(r"[1-5]", text)
                if match:
                    level = int(match.group())
                    return TaskComplexity(level)
        except Exception:
            pass
        return None

    def classify_with_explanation(
        self, prompt: str, context: Optional[str] = None,
        message_count: int = 0,
    ) -> tuple[TaskComplexity, str]:
        full_text = prompt + " " + (context or "")
        prompt_tokens = _estimate_tokens(prompt)
        entity_count = _count_entities(full_text)

        if _contains_any(full_text, CRITICAL_KEYWORDS):
            return TaskComplexity.CRITICAL, "Contém palavras-chave críticas"

        if _contains_any(full_text, COMPLEX_KEYWORDS):
            if self._history_boost():
                return TaskComplexity.CRITICAL, "Keywords complexas + histograma boost"
            return TaskComplexity.COMPLEX, "Contém palavras-chave de alta complexidade"

        if entity_count >= 3:
            return TaskComplexity.COMPLEX, f"{entity_count} entidades/projetos detectados"

        if prompt_tokens < 20:
            if _contains_any(prompt, TRIVIAL_KEYWORDS):
                return TaskComplexity.TRIVIAL, f"Prompt curto ({prompt_tokens}t) + keywords triviais"
            return TaskComplexity.SIMPLE, f"Prompt curto ({prompt_tokens}t)"

        if prompt_tokens > 500:
            if _has_code_block(prompt):
                return TaskComplexity.COMPLEX, "Prompt longo com código"
            return TaskComplexity.MEDIUM, f"Prompt longo ({prompt_tokens}t)"

        if _contains_any(full_text, SIMPLE_KEYWORDS):
            return TaskComplexity.SIMPLE, "Keywords de baixa complexidade"

        if _has_code_block(prompt):
            return TaskComplexity.MEDIUM, "Contém código"

        if entity_count >= 1:
            return TaskComplexity.MEDIUM, f"{entity_count} entidade(s) detectada(s)"

        return TaskComplexity.MEDIUM, "Fallback padrão"


# Instância global
classifier = TaskClassifier()
