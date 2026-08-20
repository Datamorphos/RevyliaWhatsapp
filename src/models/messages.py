from typing import Any

from pydantic import BaseModel, Field


class InboundWhatsAppMessage(BaseModel):
    message_id: str
    from_number: str
    phone_number_id: str | None = None
    text: str
    timestamp: str | None = None
    contact_name: str | None = None
    message_type: str = "text"
    raw: dict[str, Any] = Field(default_factory=dict)
