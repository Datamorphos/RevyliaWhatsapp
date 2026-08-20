import asyncio
import logging

from src.agents.runtime import invoke_revylia
from src.core.config import Settings, get_settings
from src.core.security import normalize_phone
from src.database.repository import WhatsAppEventRepository
from src.integrations.whatsapp.client import WhatsAppClient
from src.models.messages import InboundWhatsAppMessage


logger = logging.getLogger(__name__)


class MessageProcessor:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.events = WhatsAppEventRepository(self.settings)
        self.whatsapp = WhatsAppClient(self.settings)

    def _is_allowed(self, from_number: str) -> bool:
        allowed = self.settings.allowed_whatsapp_numbers
        if not allowed:
            return True
        normalized = normalize_phone(from_number)
        return normalized in allowed

    async def process(self, message: InboundWhatsAppMessage) -> dict:
        if not self._is_allowed(message.from_number):
            logger.warning("WhatsApp ignorado por allowlist | from_hash_only")
            return {"status": "ignored_not_allowed"}

        if len(message.text) > self.settings.revylia_max_input_chars:
            await self.whatsapp.send_text(
                to=message.from_number,
                phone_number_id=message.phone_number_id,
                text=f"El mensaje supera {self.settings.revylia_max_input_chars} caracteres.",
            )
            return {"status": "rejected_too_long"}

        claimed = await asyncio.to_thread(
            self.events.claim,
            self.settings.revylia_clinic_id,
            message.message_id,
            message.from_number,
        )
        if not claimed:
            logger.info("Webhook duplicado ignorado | message_id=%s", message.message_id)
            return {"status": "duplicate"}

        try:
            output = await asyncio.to_thread(
                invoke_revylia,
                message.text,
                thread_id=f"whatsapp:{message.from_number}",
                tenant_id=self.settings.revylia_clinic_id,
                channel="whatsapp",
                request_id=message.message_id,
                trace=True,
            )
            reply = (output.get("final_response") or "").strip()
            if not reply:
                reply = "No pude generar una respuesta. Intenta nuevamente."

            await self.whatsapp.send_text(
                to=message.from_number,
                text=reply,
                phone_number_id=message.phone_number_id,
            )
            await asyncio.to_thread(self.events.mark_completed, message.message_id, reply)
            return {
                "status": "completed",
                "executed_agents": output.get("executed_agents", []),
                "action_types": output.get("action_types", []),
                "request_id": output.get("request_id"),
            }
        except Exception as exc:
            logger.exception("Error procesando mensaje WhatsApp | message_id=%s", message.message_id)
            try:
                await asyncio.to_thread(
                    self.events.mark_failed,
                    message.message_id,
                    type(exc).__name__,
                )
            finally:
                raise
