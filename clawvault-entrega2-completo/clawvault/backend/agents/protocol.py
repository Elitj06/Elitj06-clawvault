"""
ClawVault - AgentSpeak Protocol
================================

Protocolo de comunicação compacto entre agentes. Substitui frases completas
por tags curtas, reduzindo drasticamente o consumo de tokens em orquestrações
multi-agente.

EXEMPLO DE ECONOMIA:

  Linguagem natural (243 tokens):
    "Preciso que você analise o código anexo com atenção especial a questões
    de segurança, performance e manutenibilidade. Após a análise, por favor
    sugira melhorias e classifique cada sugestão por prioridade (alta, média
    ou baixa). Me retorne em formato estruturado. Obrigado!"

  AgentSpeak (38 tokens):
    #TASK:analyze #FOCUS:sec,perf,maint #CODE:<attached>
    #OUT:suggestions+priority[H|M|L] #FMT:json

ESTRUTURA DO PROTOCOLO:
  #TAG:value         → instrução ou contexto
  &REF:id            → referência a item anterior
  !FLAG              → flag booleano
  ?QUERY:x           → pergunta/solicitação
  >NEXT:agent        → encaminhar para outro agente
  <PREV:agent        → resposta de agente anterior

CAMPOS PADRÃO:
  #TASK    → o que fazer (verbo curto)
  #CTX     → contexto necessário
  #IN      → input/dados de entrada
  #OUT     → formato esperado de saída
  #FMT     → formato (json, md, text, code)
  #PRIO    → prioridade (H=High, M=Medium, L=Low)
  #LANG    → idioma da resposta (pt, en)
  #LIMIT   → limite de tokens/linhas
  #STYLE   → estilo (concise, detailed, technical)
  #ROLE    → papel que o agente deve assumir
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
import json
import re


# ==========================================================================
# TAGS E SÍMBOLOS
# ==========================================================================

class TaskVerb(Enum):
    """Verbos curtos para ações comuns. Cada um = 1 token."""
    ANALYZE = "anl"        # analisar
    SUMMARIZE = "sum"      # resumir
    GENERATE = "gen"       # gerar
    TRANSLATE = "trn"      # traduzir
    CLASSIFY = "cls"       # classificar
    EXTRACT = "ext"        # extrair
    EDIT = "edt"           # editar
    REVIEW = "rev"         # revisar
    SEARCH = "srch"        # buscar
    DECIDE = "dec"         # decidir
    PLAN = "pln"           # planejar
    EXECUTE = "exec"       # executar
    VALIDATE = "val"       # validar
    DEBUG = "dbg"          # depurar
    REFACTOR = "rfc"       # refatorar
    DOCUMENT = "doc"       # documentar
    TEST = "tst"           # testar
    COMPARE = "cmp"        # comparar


class OutputFormat(Enum):
    """Formatos de saída. Nome curto = menos tokens."""
    JSON = "json"
    MARKDOWN = "md"
    TEXT = "txt"
    CODE = "code"
    LIST = "list"
    TABLE = "tbl"
    YAML = "yaml"
    BULLET = "bul"


class Priority(Enum):
    """Prioridade abreviada."""
    HIGH = "H"
    MEDIUM = "M"
    LOW = "L"


class Style(Enum):
    """Estilo da resposta."""
    CONCISE = "cnc"        # conciso (default entre agentes)
    DETAILED = "det"       # detalhado
    TECHNICAL = "tech"     # técnico
    SIMPLE = "smp"         # simples


# ==========================================================================
# ESTRUTURA DE MENSAGEM
# ==========================================================================

@dataclass
class AgentMessage:
    """Mensagem compacta trocada entre agentes."""

    task: Optional[str] = None          # TaskVerb ou string livre curta
    context: Optional[str] = None       # Contexto mínimo necessário
    input_data: Optional[str] = None    # Dados de entrada
    output_format: Optional[str] = None
    priority: Optional[str] = None
    language: str = "pt"                # Default: PT-BR
    max_tokens_hint: Optional[int] = None
    style: str = "cnc"                  # Concise é o default
    role: Optional[str] = None
    flags: list[str] = field(default_factory=list)
    refs: dict[str, str] = field(default_factory=dict)
    queries: list[str] = field(default_factory=list)
    next_agent: Optional[str] = None
    prev_agent: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def encode(self) -> str:
        """
        Serializa para string AgentSpeak compacta.

        Exemplo de saída:
            #TASK:anl #CTX:gymflow_schema #IN:<data>
            #OUT:json #FMT:md #PRIO:H #LANG:pt #STYLE:cnc
        """
        parts = []

        if self.task:
            parts.append(f"#TASK:{self.task}")
        if self.role:
            parts.append(f"#ROLE:{self.role}")
        if self.context:
            # Trunca contexto em 500 chars para não explodir tokens
            ctx = self.context[:500]
            parts.append(f"#CTX:{ctx}")
        if self.input_data:
            parts.append(f"#IN:{self.input_data}")
        if self.output_format:
            parts.append(f"#OUT:{self.output_format}")
        if self.priority:
            parts.append(f"#PRIO:{self.priority}")
        if self.language and self.language != "pt":
            parts.append(f"#LANG:{self.language}")
        if self.max_tokens_hint:
            parts.append(f"#LIMIT:{self.max_tokens_hint}")
        if self.style and self.style != "cnc":
            parts.append(f"#STYLE:{self.style}")
        for flag in self.flags:
            parts.append(f"!{flag}")
        for key, val in self.refs.items():
            parts.append(f"&{key}:{val}")
        for q in self.queries:
            parts.append(f"?{q}")
        if self.next_agent:
            parts.append(f">NEXT:{self.next_agent}")
        if self.prev_agent:
            parts.append(f"<PREV:{self.prev_agent}")
        for key, val in self.extra.items():
            parts.append(f"#{key.upper()}:{val}")

        return " ".join(parts)

    @classmethod
    def decode(cls, text: str) -> "AgentMessage":
        """Parseia uma string AgentSpeak de volta para objeto."""
        msg = cls()

        # Regex para capturar tokens do protocolo
        pattern = re.compile(
            r"(#\w+:[^\s#!&?<>]+)"       # #TAG:value
            r"|(![A-Z_]+)"                # !FLAG
            r"|(&\w+:[^\s#!&?<>]+)"      # &REF:id
            r"|(\?[^\s#!&?<>]+)"         # ?QUERY
            r"|(>NEXT:[\w\-]+)"           # >NEXT:agent (aceita hífens)
            r"|(<PREV:[\w\-]+)"           # <PREV:agent
        )

        for match in pattern.finditer(text):
            token = match.group(0)

            if token.startswith("#"):
                key, _, val = token[1:].partition(":")
                key_lower = key.lower()
                mapping = {
                    "task": "task",
                    "ctx": "context",
                    "in": "input_data",
                    "out": "output_format",
                    "prio": "priority",
                    "lang": "language",
                    "limit": "max_tokens_hint",
                    "style": "style",
                    "role": "role",
                }
                if key_lower in mapping:
                    attr = mapping[key_lower]
                    if attr == "max_tokens_hint":
                        try:
                            setattr(msg, attr, int(val))
                        except ValueError:
                            pass
                    else:
                        setattr(msg, attr, val)
                else:
                    msg.extra[key_lower] = val
            elif token.startswith("!"):
                msg.flags.append(token[1:])
            elif token.startswith("&"):
                key, _, val = token[1:].partition(":")
                msg.refs[key] = val
            elif token.startswith("?"):
                msg.queries.append(token[1:])
            elif token.startswith(">NEXT:"):
                msg.next_agent = token[len(">NEXT:"):]
            elif token.startswith("<PREV:"):
                msg.prev_agent = token[len("<PREV:"):]

        return msg


# ==========================================================================
# SYSTEM PROMPT COMPACTO PARA AGENTES
# ==========================================================================

# Este é o prompt que ensina o LLM a falar AgentSpeak.
# Colocamos no system prompt para ser cacheado (custa 10% do input normal).
AGENT_SYSTEM_PROMPT = """You are a ClawVault sub-agent communicating via AgentSpeak protocol.

RULES (follow strictly):
1. NO pleasantries ("hello", "thanks", "sure", "of course", etc). NEVER.
2. NO preamble or meta-commentary ("Let me analyze...", "I'll now...").
3. Output ONLY the requested content in the requested format.
4. If format is json/yaml/code, output ONLY that. No explanations outside.
5. If #LIMIT is set, respect it strictly. Prefer fewer tokens.
6. If #STYLE:cnc (concise) — use telegraphic style. Drop articles/fillers.
7. Respond in #LANG (default pt-BR) but keep technical terms in English.
8. For errors: respond with !ERROR:<code> #MSG:<brief>

INPUT PROTOCOL:
  #TASK:<verb>    action to perform (anl/sum/gen/cls/ext/rev/pln/etc)
  #CTX:<str>      context (may be truncated)
  #IN:<data>      input data
  #OUT:<fmt>      desired output format (json|md|txt|code|list|tbl)
  #PRIO:<H|M|L>   priority
  #LIMIT:<n>      max tokens for response
  #STYLE:<cnc|det|tech|smp>
  #ROLE:<str>     role to assume
  !FLAG           boolean flags (e.g. !NOEXPLAIN, !STRICT)
  &REF:<id>       reference to prior item
  ?<query>        inline question

OUTPUT: content only. No greeting, no sign-off. Raw format."""


# ==========================================================================
# HELPER: Builder fluente
# ==========================================================================

class AgentMessageBuilder:
    """Builder para construir mensagens AgentSpeak de forma legível."""

    def __init__(self):
        self._msg = AgentMessage()

    def task(self, verb: str | TaskVerb) -> "AgentMessageBuilder":
        self._msg.task = verb.value if isinstance(verb, TaskVerb) else verb
        return self

    def context(self, ctx: str) -> "AgentMessageBuilder":
        self._msg.context = ctx
        return self

    def input(self, data: str) -> "AgentMessageBuilder":
        self._msg.input_data = data
        return self

    def output(self, fmt: str | OutputFormat) -> "AgentMessageBuilder":
        self._msg.output_format = fmt.value if isinstance(fmt, OutputFormat) else fmt
        return self

    def priority(self, p: str | Priority) -> "AgentMessageBuilder":
        self._msg.priority = p.value if isinstance(p, Priority) else p
        return self

    def limit(self, n: int) -> "AgentMessageBuilder":
        self._msg.max_tokens_hint = n
        return self

    def role(self, r: str) -> "AgentMessageBuilder":
        self._msg.role = r
        return self

    def flag(self, f: str) -> "AgentMessageBuilder":
        self._msg.flags.append(f)
        return self

    def lang(self, lg: str) -> "AgentMessageBuilder":
        self._msg.language = lg
        return self

    def forward_to(self, agent: str) -> "AgentMessageBuilder":
        self._msg.next_agent = agent
        return self

    def build(self) -> AgentMessage:
        return self._msg

    def encode(self) -> str:
        return self._msg.encode()


def new_message() -> AgentMessageBuilder:
    """Factory para criar builder."""
    return AgentMessageBuilder()


# ==========================================================================
# ESTIMATIVA DE ECONOMIA
# ==========================================================================

def estimate_savings(natural_text: str, agentspeak_text: str) -> dict:
    """Compara tamanhos entre linguagem natural e AgentSpeak."""
    # Aproximação grosseira: 1 token ≈ 4 chars para texto em português
    nat_tokens = len(natural_text) // 4
    agent_tokens = len(agentspeak_text) // 4
    saved = nat_tokens - agent_tokens
    ratio = (saved / nat_tokens * 100) if nat_tokens > 0 else 0

    return {
        "natural_tokens": nat_tokens,
        "agentspeak_tokens": agent_tokens,
        "tokens_saved": saved,
        "savings_percent": round(ratio, 1),
    }
