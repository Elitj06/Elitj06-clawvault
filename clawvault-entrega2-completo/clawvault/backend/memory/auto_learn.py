"""
ClawVault - Auto-Learning Engine
=================================

Analisa cada conversa após a resposta do LLM e decide se algo
merece ser salvo no vault de conhecimentos.

CATEGORIAS DETECTADAS:
- contato: nomes, telefones, emails, relações
- decisão: decisões tomadas, escolhas, mudanças de plano
- preferência: gostos, hábitos, horários, estilos
- regra: regras de negócio, restrições, políticas
- projeto: projetos mencionados, status, atualizações
- fato: informações factuais relevantes (endereços, valores, datas)
- lição: erros, correções, aprendizados

COMO FUNCIONA:
1. Recebe a mensagem do usuário + resposta do LLM
2. Usa heurísticas rápidas para detectar se há info importante
3. Se detectou, salva automaticamente no vault (10_wiki/)
4. Se a conversa gerou output útil, salva em 20_output/
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


# ==========================================================================
# PADRÕES DE DETECÇÃO (heurísticas rápidas, sem LLM)
# ==========================================================================

# Padrões que indicam informação importante do usuário
INFO_PATTERNS = {
    "contato": [
        r"(?:meu nome é|me chamo|sou o|sou a)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        r"(?:telefone|whatsapp|celular|número)[\s:]*(?:é\s*)?(\+?\d[\d\s\-]{7,})",
        r"(?:email|e-mail|correo)[\s:]*(?:é\s*)?([\w.+-]+@[\w-]+\.[\w.]+)",
        r"(?:chamar|me liga|fala com|procurar)\s+(?:o|a)?\s*([A-Z][a-z]+)",
    ],
    "decisão": [
        r"(?:decidi|decidimos|vamos|vou|decisão\s+é|resolvi|optei)",
        r"(?:a partir de agora|de agora em diante|mudança|mudar|trocar)",
        r"(?:cancelar|cancelamento|pausar|retomar|encerrar)",
    ],
    "preferência": [
        r"(?:prefiro|gosto mais|quero sempre|nunca|sempre|odiei)",
        r"(?:horário preferido|melhor horário|disponível às|disponível para)",
        r"(?:não gosto|não quero|não precisa|não gosto de)",
    ],
    "regra": [
        r"(?:regra|política|obrigatório|proibido|não pode|deve ser|tem que)",
        r"(?:sempre que|nunca faça|quando acontecer|em caso de)",
        r"(?:fluxo é|processo é|procedimento|protocolo)",
    ],
    "projeto": [
        r"(?:projeto\s+|novo projeto|iniciativa|startup|produto\s+|app\s+|plataforma\s+)",
        r"(?:lançar|lançamento|deploy| MVP | versão\s+\d| release )",
        r"(?:cliente\s+|parceiro\s+|fornecedor\s+|investidor\s+)",
    ],
    "valor": [
        r"R\$\s*[\d.,]+",
        r"\$\s*[\d.,]+",
        r"(?:preço|valor|custo|orçamento|mensalidade)[\s:]*[\d.,]+",
    ],
}

# Padrões que indicam que a RESPOSTA do LLM contém conhecimento útil
KNOWLEDGE_PATTERNS = [
    r"(?:resumo|síntese|conclusão|ponto principal)",
    r"(?:passo\s+a\s+passo|tutorial|como\s+fazer|instruções)",
    r"(?:análise|comparação|prós\s+e\s+contras|vantagens)",
    r"(?:recomendação|sugestão|melhor\s+opção)",
]


class AutoLearner:
    """
    Motor de auto-aprendizado.
    
    Roda após cada interação e decide o que salvar no vault.
    Usa heurísticas (sem LLM) pra manter custo zero.
    """

    def __init__(self, vault_ref=None):
        self.vault = vault_ref
        self._last_save_time = {}
        self._min_interval_seconds = 30  # Não salvar mais que 1x por 30s por categoria

    def process_exchange(
        self,
        user_message: str,
        assistant_response: str,
        conversation_id: int,
    ) -> list[dict]:
        """
        Analisa uma troca user→assistant e retorna lista de coisas pra salvar.
        
        Returns:
            Lista de dicts com {title, content, layer, category, tags}
        """
        findings = []
        now = datetime.now()
        
        combined = f"{user_message}\n{assistant_response}"
        combined_lower = combined.lower()
        user_lower = user_message.lower()

        # 1. Detectar contatos
        contacts = self._extract_contacts(user_message)
        for contact in contacts:
            if self._can_save("contato", now):
                findings.append({
                    "title": f"Contato: {contact['name']}",
                    "content": self._format_contact_note(contact, user_message),
                    "layer": "wiki",
                    "category": "pessoas",
                    "tags": ["contato", contact.get("name", "").lower().replace(" ", "-")],
                })

        # 2. Detectar decisões
        if self._matches_any(user_lower, INFO_PATTERNS["decisão"]):
            if self._can_save("decisão", now):
                findings.append({
                    "title": f"Decisão: {user_message[:80]}",
                    "content": self._format_decision_note(user_message, assistant_response),
                    "layer": "wiki",
                    "category": "eventos",
                    "tags": ["decisão", "auto-aprendizado"],
                })

        # 3. Detectar preferências
        if self._matches_any(user_lower, INFO_PATTERNS["preferência"]):
            if self._can_save("preferência", now):
                findings.append({
                    "title": f"Preferência: {user_message[:80]}",
                    "content": self._format_preference_note(user_message),
                    "layer": "wiki",
                    "category": "conceitos",
                    "tags": ["preferência", "auto-aprendizado"],
                })

        # 4. Detectar regras de negócio
        if self._matches_any(combined_lower, INFO_PATTERNS["regra"]):
            if self._can_save("regra", now):
                findings.append({
                    "title": f"Regra: {user_message[:80]}",
                    "content": self._format_rule_note(user_message, assistant_response),
                    "layer": "wiki",
                    "category": "conceitos",
                    "tags": ["regra", "negócio", "auto-aprendizado"],
                })

        # 5. Detectar menções a projetos
        if self._matches_any(combined_lower, INFO_PATTERNS["projeto"]):
            if self._can_save("projeto", now):
                findings.append({
                    "title": f"Projeto: {user_message[:80]}",
                    "content": self._format_project_note(user_message, assistant_response),
                    "layer": "wiki",
                    "category": "projetos",
                    "tags": ["projeto", "auto-aprendizado"],
                })

        # 6. Detectar valores/preços
        if self._matches_any(combined_lower, INFO_PATTERNS["valor"]):
            if self._can_save("valor", now):
                findings.append({
                    "title": f"Valor: {user_message[:80]}",
                    "content": self._format_value_note(user_message, assistant_response),
                    "layer": "wiki",
                    "category": "conceitos",
                    "tags": ["financeiro", "auto-aprendizado"],
                })

        # 7. Se a resposta do assistente é conhecimento útil (longa e estruturada)
        if len(assistant_response) > 500 and self._matches_any(assistant_response.lower(), KNOWLEDGE_PATTERNS):
            if self._can_save("conhecimento", now):
                findings.append({
                    "title": f"Conhecimento: {user_message[:60]}",
                    "content": self._format_knowledge_note(user_message, assistant_response),
                    "layer": "output",
                    "category": "drafts",
                    "tags": ["conhecimento", "auto-aprendizado"],
                })

        return findings

    def save_findings(self, findings: list[dict]) -> list[str]:
        """Salva as descobertas no vault e retorna os paths."""
        saved = []
        if not self.vault:
            return saved

        for f in findings:
            try:
                filepath = self.vault.save_wiki(
                    title=f["title"],
                    content=f["content"],
                    category=f.get("category"),
                    tags=f.get("tags"),
                )
                saved.append(str(filepath))
            except Exception as e:
                # Log mas não quebra o fluxo
                print(f"[AutoLearn] Erro ao salvar: {e}")

        return saved

    # ==========================================================================
    # HELPERS PRIVADOS
    # ==========================================================================

    def _matches_any(self, text: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _extract_contacts(self, text: str) -> list[dict]:
        """Extrai contatos da mensagem do usuário."""
        contacts = []
        
        # Nome
        name_match = re.search(
            r"(?:meu nome é|me chamo|sou o|sou a)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            text
        )
        name = name_match.group(1) if name_match else None

        # Telefone
        phone_match = re.search(
            r"(?:telefone|whatsapp|celular|número)[\s:]*(?:é\s*)?(\+?\d[\d\s\-]{7,})",
            text, re.IGNORECASE
        )
        phone = phone_match.group(1).strip() if phone_match else None

        # Email
        email_match = re.search(
            r"[\w.+-]+@[\w-]+\.[\w.]+", text
        )
        email = email_match.group(0) if email_match else None

        if name or phone or email:
            contacts.append({
                "name": name,
                "phone": phone,
                "email": email,
            })

        return contacts

    def _can_save(self, category: str, now: datetime) -> bool:
        """Evita salvar a mesma categoria muitas vezes seguidas."""
        last = self._last_save_time.get(category)
        if last and (now - last).total_seconds() < self._min_interval_seconds:
            return False
        self._last_save_time[category] = now
        return True

    def _format_contact_note(self, contact: dict, context: str) -> str:
        lines = [f"# Contato: {contact.get('name', 'Desconhecido')}", ""]
        if contact.get("name"):
            lines.append(f"- **Nome:** {contact['name']}")
        if contact.get("phone"):
            lines.append(f"- **Telefone:** {contact['phone']}")
        if contact.get("email"):
            lines.append(f"- **Email:** {contact['email']}")
        lines.append(f"- **Contexto:** {context[:200]}")
        lines.append(f"- **Registrado em:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"- **Tags:** #contato #auto-aprendizado")
        return "\n".join(lines)

    def _format_decision_note(self, user_msg: str, response: str) -> str:
        return (
            f"# Decisão Registrada\n\n"
            f"**O que foi decidido:** {user_msg[:300]}\n\n"
            f"**Contexto da resposta:** {response[:300]}\n\n"
            f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"**Tags:** #decisão #auto-aprendizado"
        )

    def _format_preference_note(self, user_msg: str) -> str:
        return (
            f"# Preferência Registrada\n\n"
            f"**Preferência:** {user_msg[:300]}\n\n"
            f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"**Tags:** #preferência #auto-aprendizado"
        )

    def _format_rule_note(self, user_msg: str, response: str) -> str:
        return (
            f"# Regra de Negócio\n\n"
            f"**Solicitação:** {user_msg[:200]}\n\n"
            f"**Regra definida:** {response[:300]}\n\n"
            f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"**Tags:** #regra #negócio #auto-aprendizado"
        )

    def _format_project_note(self, user_msg: str, response: str) -> str:
        return (
            f"# Menção de Projeto\n\n"
            f"**Contexto:** {user_msg[:200]}\n\n"
            f"**Detalhes:** {response[:300]}\n\n"
            f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"**Tags:** #projeto #auto-aprendizado"
        )

    def _format_value_note(self, user_msg: str, response: str) -> str:
        return (
            f"# Informação Financeira\n\n"
            f"**Contexto:** {user_msg[:200]}\n\n"
            f"**Detalhes:** {response[:300]}\n\n"
            f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"**Tags:** #financeiro #auto-aprendizado"
        )

    def _format_knowledge_note(self, user_msg: str, response: str) -> str:
        return (
            f"# Conhecimento Útil\n\n"
            f"**Pergunta:** {user_msg[:200]}\n\n"
            f"**Resposta:**\n{response[:800]}\n\n"
            f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"**Tags:** #conhecimento #auto-aprendizado"
        )


# Instância global
auto_learner = AutoLearner()
