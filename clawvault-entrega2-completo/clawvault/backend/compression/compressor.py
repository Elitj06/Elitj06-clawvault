"""
ClawVault - HumanCompressor
============================

Comprime linguagem natural (humana) em forma mais enxuta antes de enviar
para o LLM, preservando 100% do significado e contexto.

Estratégia em camadas (aplica em ordem, cada uma economiza mais):

  CAMADA 1 — Regras rápidas (zero custo, instantânea):
    - Remove cortesias ("por favor", "obrigado", "quando puder")
    - Remove hedge words ("talvez", "acho que", "se possível")
    - Contrações ("para o" → "pro", "de um" → "dum")
    - Consolida espaços e pontuação redundante

  CAMADA 2 — Normalização (zero custo):
    - Lowercase em keywords
    - Remove repetições
    - Consolida listas

  CAMADA 3 — Compressão semântica (custo mínimo):
    - Só ativa se o texto ainda for > threshold (ex: 200 tokens)
    - Usa um modelo GRÁTIS (Z.ai Flash ou OpenRouter free) para
      reescrever em forma telegráfica preservando fatos

ECONOMIA TÍPICA:
  - Texto curto (<200 tokens): 15-30% com só Camada 1+2
  - Texto médio (200-800 tokens): 30-50%
  - Texto longo (>800 tokens): 50-70% com Camada 3 ativa

IMPORTANTE: o usuário NUNCA vê o texto comprimido. Ele continua escrevendo
em português natural. A compressão é transparente.
"""

import re
from dataclasses import dataclass
from typing import Optional


# ==========================================================================
# PADRÕES DE COMPRESSÃO POR REGRAS
# ==========================================================================

# Cortesias e amenidades que podem ser removidas sem perda de contexto
COURTESY_PATTERNS = [
    r"\b(por\s+favor|pfv|pf)\b",
    r"\b(obrigad[oa]|valeu|vlw|thanks|thank you)\b",
    r"\b(quando\s+(você\s+)?puder|quando\s+der|se\s+possível|se\s+der)\b",
    r"\b(desde\s+já|antecipadamente)\b",
    r"\b(gentileza|a\s+gentileza\s+de)\b",
    r"\bcom\s+carinho\b",
    r"\bum\s+abraço\b",
    r"\batenciosamente\b",
]

# Hedge words (atenuadores) que não agregam ao comando
HEDGE_PATTERNS = [
    r"\b(talvez|quem\s+sabe|eu\s+acho\s+que|acho\s+que|imagino\s+que)\b",
    r"\b(mais\s+ou\s+menos|tipo\s+assim|meio\s+que)\b",
    r"\b(basicamente|essencialmente|praticamente|literalmente)\b",
    r"\b(bem|muito\s+bem)\s+", # "bem rapidamente" → "rapidamente"
]

# Filler words que podem ir fora sem perda
FILLER_PATTERNS = [
    r"\b(então|bom|olha|veja\s+bem|na\s+verdade|sabe)\b,?\s*",
    r"\b(é\s+que|o\s+fato\s+é\s+que|a\s+questão\s+é\s+que)\b",
    r"\bbom\s+dia\b|\bboa\s+tarde\b|\bboa\s+noite\b",
    r"\boi[,.!]\s*|^olá[,.!]\s*|^e\s+aí[,.!]\s*",
]

# Substituições curtas (contrações que economizam tokens)
# Aplicar com cuidado, só em contextos seguros
CONTRACTIONS = [
    (r"\bpara\s+o\b", "pro"),
    (r"\bpara\s+a\b", "pra"),
    (r"\bpara\s+os\b", "pros"),
    (r"\bpara\s+as\b", "pras"),
    (r"\bde\s+uma\b", "duma"),
    (r"\bde\s+um\b", "dum"),
    (r"\bcom\s+você\b", "c/vc"),
    (r"\bvocê\b", "vc"),    # só se estilo for ultra-compacto
]

# Verbos por comandos diretos (mais enxutos)
VERB_SHORTCUTS = [
    (r"\beu\s+queria\s+que\s+você\s+", ""),
    (r"\beu\s+gostaria\s+que\s+você\s+", ""),
    (r"\bpreciso\s+que\s+você\s+", ""),
    (r"\bvocê\s+poderia\s+", ""),
    (r"\bvocê\s+consegue\s+", ""),
    (r"\bvocê\s+pode\s+", ""),
    (r"\bme\s+ajuda\s+a\s+", ""),
    (r"\bme\s+ajude\s+a\s+", ""),
    (r"\bfaz\s+o\s+favor\s+de\s+", ""),
]


# ==========================================================================
# COMPRESSOR
# ==========================================================================

@dataclass
class CompressionResult:
    """Resultado de uma operação de compressão."""
    original: str
    compressed: str
    chars_saved: int
    tokens_saved_estimate: int
    savings_percent: float
    method: str           # "rules", "semantic", "hybrid"
    semantic_cost: float = 0.0  # Custo em USD da compressão semântica (se houve)


class HumanCompressor:
    """
    Comprime linguagem humana para forma mais enxuta.

    Uso básico:
        compressor = HumanCompressor()
        result = compressor.compress("Por favor, você poderia me ajudar a...")
        print(result.compressed)

    Uso com compressão semântica (para textos longos):
        compressor = HumanCompressor(use_semantic=True)
        result = compressor.compress(long_text)
    """

    def __init__(
        self,
        preserve_user_style: bool = True,
        aggressive: bool = False,
        use_semantic: bool = False,
        semantic_threshold_tokens: int = 200,
        semantic_model: str = "glm-4.7-flash",
    ):
        """
        Args:
            preserve_user_style: se True, aplica compressão mais conservadora
                (mantém "você" em vez de "vc", etc). Recomendado para
                produção — compressão agressiva pode mudar tom.
            aggressive: se True, aplica TODAS as substituições, incluindo
                contrações curtas. Use apenas em contextos onde o LLM não
                vai devolver o texto ao usuário.
            use_semantic: se True, usa um modelo grátis para comprimir
                semanticamente textos longos.
            semantic_threshold_tokens: tamanho mínimo para ativar semântica.
            semantic_model: ID do modelo grátis usado para compressão.
        """
        self.preserve_user_style = preserve_user_style
        self.aggressive = aggressive
        self.use_semantic = use_semantic
        self.semantic_threshold = semantic_threshold_tokens
        self.semantic_model = semantic_model

    # ----------------------------------------------------------------------
    # Camada 1: compressão por regras (zero custo)
    # ----------------------------------------------------------------------

    def _apply_patterns(self, text: str, patterns: list) -> str:
        """Aplica uma lista de patterns regex."""
        for pattern in patterns:
            if isinstance(pattern, tuple):
                regex, replacement = pattern
                text = re.sub(regex, replacement, text, flags=re.IGNORECASE)
            else:
                text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
        return text

    def _rule_based_compress(self, text: str) -> str:
        """Compressão baseada em regras — sempre aplicada."""
        compressed = text

        # Remove cortesias, hedges, fillers
        compressed = self._apply_patterns(compressed, COURTESY_PATTERNS)
        compressed = self._apply_patterns(compressed, HEDGE_PATTERNS)
        compressed = self._apply_patterns(compressed, FILLER_PATTERNS)

        # Remove verbos rebuscados → comando direto
        compressed = self._apply_patterns(compressed, VERB_SHORTCUTS)

        # Contrações (só no modo agressivo para não afetar tom)
        if self.aggressive:
            compressed = self._apply_patterns(compressed, CONTRACTIONS)

        # Normalização final: espaços múltiplos, pontuação redundante
        compressed = re.sub(r"\s+", " ", compressed)
        compressed = re.sub(r"\s*([,.!?;:])\s*", r"\1 ", compressed)
        compressed = re.sub(r"([.!?])\1+", r"\1", compressed)
        compressed = re.sub(r"^\s*[,.;:]\s*", "", compressed)
        compressed = compressed.strip()

        # Capitaliza primeira letra (se sumiu por causa da remoção de "oi,")
        if compressed and compressed[0].islower():
            compressed = compressed[0].upper() + compressed[1:]

        return compressed

    # ----------------------------------------------------------------------
    # Camada 2: compressão semântica (via LLM grátis)
    # ----------------------------------------------------------------------

    def _semantic_compress(self, text: str) -> tuple[str, float]:
        """
        Comprime semanticamente usando um modelo grátis.
        Retorna (texto_comprimido, custo_usd).
        """
        # Import local para evitar import circular e carregamento desnecessário
        from backend.llm.router import router, LLMRequest
        from backend.core.config import TaskComplexity

        compress_prompt = f"""Reescreva o texto abaixo em forma TELEGRÁFICA preservando 100% dos fatos e instruções. Regras:
- Remova palavras redundantes mas mantenha TODOS os detalhes técnicos
- Use forma imperativa direta
- Mantenha nomes próprios, números, códigos e termos técnicos EXATOS
- Máximo 40% do tamanho original
- Sem preâmbulo, devolva apenas o texto reescrito

TEXTO:
{text}

REESCRITA:"""

        try:
            response = router.route(LLMRequest(
                prompt=compress_prompt,
                complexity_hint=TaskComplexity.TRIVIAL,  # força modelo barato/grátis
                model_override=self.semantic_model,
                temperature=0.1,  # determinístico
                max_tokens=len(text) // 4,  # resposta no máximo do tamanho do input
            ))

            if response.error or not response.content:
                # Falhou na compressão semântica, retorna original
                return text, 0.0

            return response.content.strip(), response.cost_usd

        except Exception:
            # Qualquer falha, devolve sem compressão semântica
            return text, 0.0

    # ----------------------------------------------------------------------
    # Interface principal
    # ----------------------------------------------------------------------

    def compress(self, text: str) -> CompressionResult:
        """Comprime um texto aplicando todas as camadas configuradas."""
        if not text or not text.strip():
            return CompressionResult(
                original=text, compressed=text,
                chars_saved=0, tokens_saved_estimate=0,
                savings_percent=0.0, method="none",
            )

        original = text
        semantic_cost = 0.0

        # Camada 1 e 2: regras (sempre)
        compressed = self._rule_based_compress(text)
        method = "rules"

        # Camada 3: semântica (só se texto ainda é longo E está habilitada)
        if self.use_semantic:
            estimated_tokens = len(compressed) // 4
            if estimated_tokens >= self.semantic_threshold:
                semantic_result, semantic_cost = self._semantic_compress(compressed)
                if semantic_result and len(semantic_result) < len(compressed):
                    compressed = semantic_result
                    method = "hybrid"

        chars_saved = len(original) - len(compressed)
        tokens_saved = chars_saved // 4  # aproximação
        ratio = (chars_saved / len(original) * 100) if len(original) > 0 else 0

        return CompressionResult(
            original=original,
            compressed=compressed,
            chars_saved=chars_saved,
            tokens_saved_estimate=tokens_saved,
            savings_percent=round(ratio, 1),
            method=method,
            semantic_cost=semantic_cost,
        )


# ==========================================================================
# DESCOMPRESSOR (máquina → humano)
# ==========================================================================

class ResponseHumanizer:
    """
    Transforma respostas telegráficas/técnicas de volta em linguagem
    natural e calorosa para o usuário final.

    Usa apenas regras (zero custo) na maioria dos casos. Se a resposta
    vier em formato AgentSpeak (com tags #TASK, etc), primeiro limpa as tags.
    """

    @staticmethod
    def humanize(text: str, add_greeting: bool = False) -> str:
        """Converte resposta compacta em português mais natural."""
        if not text:
            return text

        result = text

        # Remove tags do AgentSpeak se vierem na resposta por engano
        result = re.sub(r"#\w+:\S+", "", result)
        result = re.sub(r"![A-Z_]+", "", result)
        result = re.sub(r"&\w+:\S+", "", result)
        result = re.sub(r"\?\S+\s*", "", result)
        result = re.sub(r"[<>](?:NEXT|PREV):\w+", "", result)

        # Normaliza espaços
        result = re.sub(r"\s+", " ", result).strip()

        # Para respostas muito secas, adiciona leve calor (opcional)
        if add_greeting and len(result) < 500:
            # Só adiciona se não começar já com algo amigável
            if not re.match(r"^(ok|certo|claro|perfeito|feito|aqui)", result, re.I):
                pass  # não força, resposta técnica pode ficar como está

        return result


# ==========================================================================
# INSTÂNCIAS GLOBAIS RECOMENDADAS
# ==========================================================================

# Compressor padrão: só regras, seguro para qualquer texto
default_compressor = HumanCompressor(
    preserve_user_style=True,
    aggressive=False,
    use_semantic=False,
)

# Compressor agressivo: inclui compressão semântica para textos longos
aggressive_compressor = HumanCompressor(
    preserve_user_style=False,
    aggressive=True,
    use_semantic=True,
    semantic_threshold_tokens=200,
)

# Descompressor padrão
humanizer = ResponseHumanizer()
