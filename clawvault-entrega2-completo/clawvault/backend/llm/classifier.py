"""
ClawVault - Classificador de Complexidade
==========================================

Analisa um prompt do usuário e decide o nível de complexidade da tarefa
para que o roteador escolha o modelo mais adequado. Usa uma abordagem
híbrida: heurísticas rápidas primeiro, e se não bastar, um LLM barato
(Gemini Flash Lite) decide.

Isto economiza muito token porque evita chamar Opus para tarefas triviais.
"""

import re
from typing import Optional

from backend.core.config import TaskComplexity


# ==========================================================================
# HEURÍSTICAS RÁPIDAS (sem chamar LLM)
# ==========================================================================

# Palavras-chave que indicam tarefa TRIVIAL (formatação, extração simples)
TRIVIAL_KEYWORDS = [
    "liste", "lista", "list",
    "formate", "formatar", "format",
    "extraia", "extrair", "extract",
    "converta", "converter", "convert",
    "traduza palavra", "palavra em inglês", "palavra em português",
    "qual a capital", "qual o dia",
    "quantas letras", "quantos caracteres",
]

# Saudações ultra-curvas → sempre TRIVIAL
GREETING_PATTERNS = [
    r"^(oi|olá|ola|hey|hello|hi|eai|e ai|fala|beleza|blz|tudo bem|td bem|bom dia|boa tarde|boa noite)[\s!.,?]*$",
]

# Palavras-chave que indicam tarefa SIMPLES
SIMPLE_KEYWORDS = [
    "resuma", "resumir", "summarize",
    "o que é", "o que significa",
    "explique rapidamente", "explain briefly",
    "traduza", "translate",
    "corrija gramática", "fix grammar",
    "qual a diferença entre",
]

# Palavras-chave que indicam tarefa COMPLEXA
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

# Palavras-chave que indicam tarefa CRÍTICA
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


def _contains_any(text: str, keywords: list[str]) -> bool:
    """Verifica se o texto contém alguma das palavras-chave (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _has_code_block(text: str) -> bool:
    """Detecta se o prompt contém código."""
    return bool(re.search(r"```|def |class |function |import |require\(", text))


def _estimate_tokens(text: str) -> int:
    """Estimativa simples de tokens (1 token ≈ 4 caracteres em média)."""
    return len(text) // 4


# ==========================================================================
# CLASSIFICADOR HÍBRIDO
# ==========================================================================

class TaskClassifier:
    """
    Classifica tarefas em 5 níveis de complexidade.

    Usa heurísticas primeiro (grátis e instantâneo). Se o resultado
    for ambíguo, consulta um LLM barato (opcional).
    """

    def __init__(self, use_llm_fallback: bool = False):
        self.use_llm_fallback = use_llm_fallback

    def classify(self, prompt: str, context: Optional[str] = None) -> TaskComplexity:
        """
        Classifica o prompt em um nível de complexidade.

        Args:
            prompt: O prompt do usuário
            context: Contexto adicional (mensagens anteriores, memória)

        Returns:
            TaskComplexity (TRIVIAL, SIMPLE, MEDIUM, COMPLEX, CRITICAL)
        """
        full_text = prompt + " " + (context or "")

        # Regra 0: saudações ultra-curtas são sempre TRIVIAL
        prompt_stripped = prompt.strip().lower()
        for pattern in GREETING_PATTERNS:
            if re.match(pattern, prompt_stripped, re.IGNORECASE):
                return TaskComplexity.TRIVIAL

        # Regra 1: palavras-chave críticas sempre ganham
        if _contains_any(full_text, CRITICAL_KEYWORDS):
            return TaskComplexity.CRITICAL

        # Regra 2: palavras-chave de complexidade
        if _contains_any(full_text, COMPLEX_KEYWORDS):
            return TaskComplexity.COMPLEX

        # Regra 3: prompt muito curto = provavelmente simples
        prompt_tokens = _estimate_tokens(prompt)
        if prompt_tokens < 20:
            if _contains_any(prompt, TRIVIAL_KEYWORDS):
                return TaskComplexity.TRIVIAL
            return TaskComplexity.SIMPLE

        # Regra 4: prompt muito longo = provavelmente médio ou complexo
        if prompt_tokens > 500:
            if _has_code_block(prompt):
                return TaskComplexity.COMPLEX
            return TaskComplexity.MEDIUM

        # Regra 5: keywords simples
        if _contains_any(full_text, SIMPLE_KEYWORDS):
            return TaskComplexity.SIMPLE

        # Regra 6: contém código = pelo menos MEDIUM
        if _has_code_block(prompt):
            return TaskComplexity.MEDIUM

        # Fallback: MEDIUM (o "default seguro")
        return TaskComplexity.MEDIUM

    def classify_with_explanation(
        self, prompt: str, context: Optional[str] = None
    ) -> tuple[TaskComplexity, str]:
        """Versão que também retorna o motivo da classificação (para debug)."""
        full_text = prompt + " " + (context or "")
        prompt_tokens = _estimate_tokens(prompt)

        if _contains_any(full_text, CRITICAL_KEYWORDS):
            return TaskComplexity.CRITICAL, "Contém palavras-chave críticas"

        if _contains_any(full_text, COMPLEX_KEYWORDS):
            return TaskComplexity.COMPLEX, "Contém palavras-chave de alta complexidade"

        if prompt_tokens < 20:
            if _contains_any(prompt, TRIVIAL_KEYWORDS):
                return TaskComplexity.TRIVIAL, f"Prompt curto ({prompt_tokens} tokens) + keywords triviais"
            return TaskComplexity.SIMPLE, f"Prompt curto ({prompt_tokens} tokens)"

        if prompt_tokens > 500:
            if _has_code_block(prompt):
                return TaskComplexity.COMPLEX, "Prompt longo com código"
            return TaskComplexity.MEDIUM, f"Prompt longo ({prompt_tokens} tokens)"

        if _contains_any(full_text, SIMPLE_KEYWORDS):
            return TaskComplexity.SIMPLE, "Keywords de baixa complexidade"

        if _has_code_block(prompt):
            return TaskComplexity.MEDIUM, "Contém código"

        return TaskComplexity.MEDIUM, "Fallback padrão"


# Instância global
classifier = TaskClassifier()
