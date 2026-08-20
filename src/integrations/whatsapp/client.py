import logging

import httpx

from src.core.config import Settings, get_settings


logger = logging.getLogger(__name__)


def split_whatsapp_text(text: str, limit: int = 3500) -> list[str]:
    clean = (text or "").strip()
    if not clean:
        return ["No pude generar una respuesta. Intenta nuevamente."]
    chunks = []
    while len(clean) > limit:
        split_at = clean.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = clean.rfind(" ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(clean[:split_at].strip())
        clean = clean[split_at:].strip()
    if clean:
        chunks.append(clean)
    return chunks


class WhatsAppClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.require_whatsapp_send()

    async def send_text(
        self,
        *,
        to: str,
        text: str,
        phone_number_id: str | None = None,
    ) -> list[dict]:
        chunks = split_whatsapp_text(text)
        if not self.settings.whatsapp_send_enabled:
            for chunk in chunks:
                logger.info("WhatsApp simulado -> %s | %s", to, chunk)
            return [{"simulated": True, "to": to, "text": chunk} for chunk in chunks]

        sender_phone_id = phone_number_id or self.settings.whatsapp_phone_number_id
        if not sender_phone_id:
            raise RuntimeError(
                "No hay phone_number_id en el webhook ni WHATSAPP_PHONE_NUMBER_ID configurado"
            )

        url = (
            f"https://graph.facebook.com/{self.settings.meta_graph_api_version}/"
            f"{sender_phone_id}/messages"
        )
        headers = {
            "Authorization": f"Bearer {self.settings.whatsapp_access_token}",
            "Content-Type": "application/json",
        }
        responses = []
        async with httpx.AsyncClient(timeout=25.0) as client:
            for chunk in chunks:
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": to,
                    "type": "text",
                    "text": {"preview_url": False, "body": chunk},
                }
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                responses.append(response.json())
        return responses
