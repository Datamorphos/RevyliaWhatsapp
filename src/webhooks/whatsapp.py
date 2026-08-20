import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from src.core.config import get_settings
from src.integrations.whatsapp.parser import parse_whatsapp_messages
from src.integrations.whatsapp.signature import verify_meta_signature
from src.services.message_processor import MessageProcessor


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp"])


@router.get("", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    settings = get_settings()
    if (
        hub_mode == "subscribe"
        and hub_verify_token == settings.whatsapp_verify_token
        and hub_challenge is not None
    ):
        return PlainTextResponse(hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("")
async def receive_webhook(request: Request):
    settings = get_settings()
    settings.require_meta_signature()
    raw_body = await request.body()

    if settings.verify_meta_signature:
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_meta_signature(raw_body, signature, settings.meta_app_secret or ""):
            raise HTTPException(status_code=401, detail="Invalid Meta signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    messages = parse_whatsapp_messages(payload)
    if not messages:
        return {"received": True, "processable_messages": 0}

    processor = MessageProcessor(settings)
    results = []
    for message in messages:
        results.append(await processor.process(message))

    return {
        "received": True,
        "processable_messages": len(messages),
        "results": results,
    }
