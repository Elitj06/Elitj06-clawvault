"""
ClawVault - Cliente Evolution API (WhatsApp)
=============================================

Integração com o Evolution API, a solução mais usada no Brasil para
automatizar WhatsApp via Baileys. Roda self-hosted (grátis).

COMO FUNCIONA:
  Evolution API é um servidor Node.js que mantém conexão com o WhatsApp
  via Baileys (biblioteca que simula um cliente WhatsApp Web). Ele expõe
  uma API REST simples e envia webhooks quando chegam mensagens.

FLUXO:
  1. Você instala Evolution API no seu VPS (docs abaixo)
  2. Cria uma "instância" via API (recebe um QR Code)
  3. Escaneia o QR Code no seu celular (WhatsApp → Dispositivos Conectados)
  4. Configura o webhook apontando para o ClawVault
  5. Pronto! Mensagens recebidas disparam webhook → ClawVault responde
     automaticamente via LLM

INSTALAÇÃO DA EVOLUTION API NO VPS:
  # Docker (recomendado)
  docker run -d \\
    --name evolution \\
    -p 8080:8080 \\
    -v evolution_data:/evolution/instances \\
    -e AUTHENTICATION_API_KEY=SUA_API_KEY_FORTE_AQUI \\
    atendai/evolution-api:latest

  Docs oficiais: https://doc.evolution-api.com/

⚠️  AVISOS IMPORTANTES:
  - Evolution API usa conexão NÃO-OFICIAL (Baileys). Meta pode banir o número.
  - Use número DEDICADO, nunca seu número pessoal principal.
  - "Aqueça" o número: envie mensagens graduais nos primeiros dias.
  - Não envie spam. Limite: ~100 mensagens/dia em números novos.
"""

import os
import requests
from dataclasses import dataclass
from typing import Optional, Any


# ==========================================================================
# CONFIGURAÇÃO
# ==========================================================================

@dataclass
class EvolutionConfig:
    """Configuração de conexão com Evolution API."""
    base_url: str = ""           # ex: http://localhost:8080
    api_key: str = ""            # AUTHENTICATION_API_KEY configurada no Evolution
    instance_name: str = "clawvault"  # nome da instância (canal)
    default_country_code: str = "55"  # Brasil

    @classmethod
    def from_env(cls) -> "EvolutionConfig":
        return cls(
            base_url=os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080"),
            api_key=os.getenv("EVOLUTION_API_KEY", ""),
            instance_name=os.getenv("EVOLUTION_INSTANCE", "clawvault"),
            default_country_code=os.getenv("EVOLUTION_COUNTRY_CODE", "55"),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)


# ==========================================================================
# CLIENTE
# ==========================================================================

class EvolutionClient:
    """
    Cliente para interagir com Evolution API.

    Uso básico:
        client = EvolutionClient()
        client.create_instance()         # 1ª vez
        qr = client.get_qrcode()          # mostra QR Code
        # (escaneie com o celular)
        client.send_text("5521999999999", "Olá do ClawVault!")
    """

    def __init__(self, config: Optional[EvolutionConfig] = None):
        self.config = config or EvolutionConfig.from_env()

    # ----------------------------------------------------------------------
    # Infraestrutura
    # ----------------------------------------------------------------------

    def _headers(self) -> dict:
        return {
            "apikey": self.config.api_key,
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        base = self.config.base_url.rstrip("/")
        return f"{base}{path}"

    def _normalize_phone(self, phone: str) -> str:
        """
        Normaliza um número para o formato internacional sem +.
        Ex: '21999999999' → '5521999999999'
            '(21) 99999-9999' → '5521999999999'
        """
        cleaned = "".join(c for c in phone if c.isdigit())
        # Se não começa com código do país, adiciona
        if len(cleaned) <= 11:  # número BR sem código (DDD + 9 dígitos)
            cleaned = self.config.default_country_code + cleaned
        return cleaned

    # ----------------------------------------------------------------------
    # Gerenciamento de instância
    # ----------------------------------------------------------------------

    def is_online(self) -> bool:
        """Verifica se o servidor Evolution está respondendo."""
        try:
            r = requests.get(self._url("/"), timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def create_instance(self, webhook_url: Optional[str] = None) -> dict:
        """
        Cria uma nova instância no Evolution API.

        Args:
            webhook_url: URL onde o Evolution vai enviar webhooks
                         (ex: http://seu-clawvault.com/api/whatsapp/webhook)
        """
        payload = {
            "instanceName": self.config.instance_name,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
        }
        if webhook_url:
            payload["webhook"] = {
                "url": webhook_url,
                "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
            }

        r = requests.post(
            self._url("/instance/create"),
            headers=self._headers(),
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def get_qrcode(self) -> dict:
        """Retorna o QR Code para conectar o WhatsApp."""
        r = requests.get(
            self._url(f"/instance/connect/{self.config.instance_name}"),
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def get_connection_state(self) -> dict:
        """Verifica o status da conexão (conectado/desconectado/qrcode)."""
        r = requests.get(
            self._url(f"/instance/connectionState/{self.config.instance_name}"),
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def list_instances(self) -> list:
        """Lista todas as instâncias existentes."""
        r = requests.get(
            self._url("/instance/fetchInstances"),
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else [data]

    def delete_instance(self) -> dict:
        """Remove a instância atual."""
        r = requests.delete(
            self._url(f"/instance/delete/{self.config.instance_name}"),
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def logout_instance(self) -> dict:
        """Desconecta o WhatsApp da instância (não apaga a instância)."""
        r = requests.delete(
            self._url(f"/instance/logout/{self.config.instance_name}"),
            headers=self._headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    # ----------------------------------------------------------------------
    # Envio de mensagens
    # ----------------------------------------------------------------------

    def send_text(
        self,
        phone: str,
        text: str,
        delay_ms: int = 1200,
        quoted_message_id: Optional[str] = None,
    ) -> dict:
        """
        Envia mensagem de texto para um número.

        Args:
            phone: número em qualquer formato (normalizado internamente)
            text: conteúdo da mensagem
            delay_ms: delay antes de enviar (simula "digitando")
            quoted_message_id: se quer responder a uma mensagem específica

        Returns: resposta da API Evolution
        """
        normalized = self._normalize_phone(phone)

        payload = {
            "number": normalized,
            "text": text,
            "delay": delay_ms,
        }
        if quoted_message_id:
            payload["quoted"] = {"key": {"id": quoted_message_id}}

        r = requests.post(
            self._url(f"/message/sendText/{self.config.instance_name}"),
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def send_audio(self, phone: str, audio_base64_or_url: str) -> dict:
        """Envia áudio (base64 ou URL pública)."""
        normalized = self._normalize_phone(phone)
        payload = {
            "number": normalized,
            "audio": audio_base64_or_url,
        }
        r = requests.post(
            self._url(f"/message/sendWhatsAppAudio/{self.config.instance_name}"),
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def send_image(
        self, phone: str, image_base64_or_url: str, caption: str = ""
    ) -> dict:
        """Envia imagem com legenda opcional."""
        normalized = self._normalize_phone(phone)
        payload = {
            "number": normalized,
            "mediatype": "image",
            "media": image_base64_or_url,
            "caption": caption,
        }
        r = requests.post(
            self._url(f"/message/sendMedia/{self.config.instance_name}"),
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def send_typing(self, phone: str, duration_ms: int = 2000) -> dict:
        """Simula 'digitando...' por N ms (melhora percepção humana)."""
        normalized = self._normalize_phone(phone)
        payload = {
            "number": normalized,
            "presence": "composing",
            "delay": duration_ms,
        }
        try:
            r = requests.post(
                self._url(f"/chat/sendPresence/{self.config.instance_name}"),
                headers=self._headers(),
                json=payload,
                timeout=5,
            )
            return r.json() if r.ok else {}
        except Exception:
            return {}

    def mark_as_read(self, remote_jid: str, message_id: str) -> dict:
        """Marca uma mensagem como lida (✓✓ azul)."""
        payload = {
            "readMessages": [{"remoteJid": remote_jid, "id": message_id}],
        }
        try:
            r = requests.post(
                self._url(f"/chat/markMessageAsRead/{self.config.instance_name}"),
                headers=self._headers(),
                json=payload,
                timeout=5,
            )
            return r.json() if r.ok else {}
        except Exception:
            return {}


# ==========================================================================
# INSTÂNCIA GLOBAL
# ==========================================================================

evolution_client = EvolutionClient()
