from typing import Any

from src.models.messages import InboundWhatsAppMessage


def parse_whatsapp_messages(payload: dict[str, Any]) -> list[InboundWhatsAppMessage]:
    """Parsea únicamente mensajes de texto. Statuses y multimedia se ignoran."""
    parsed: list[InboundWhatsAppMessage] = []
    if payload.get("object") != "whatsapp_business_account":
        return parsed

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") not in {None, "messages"}:
                continue
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")
            contacts_by_wa = {
                item.get("wa_id"): item.get("profile", {}).get("name")
                for item in value.get("contacts", [])
                if item.get("wa_id")
            }

            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue
                message_id = message.get("id")
                from_number = message.get("from")
                text = message.get("text", {}).get("body")
                if not message_id or not from_number or not text:
                    continue
                parsed.append(
                    InboundWhatsAppMessage(
                        message_id=message_id,
                        from_number=from_number,
                        phone_number_id=phone_number_id,
                        text=text.strip(),
                        timestamp=message.get("timestamp"),
                        contact_name=contacts_by_wa.get(from_number),
                        message_type="text",
                        raw=message,
                    )
                )
    return parsed
