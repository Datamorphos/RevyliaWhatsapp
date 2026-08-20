from src.integrations.whatsapp.parser import parse_whatsapp_messages


def test_parse_text_message():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": "123"},
                    "contacts": [{"wa_id": "573001234567", "profile": {"name": "Ana"}}],
                    "messages": [{
                        "id": "wamid.1",
                        "from": "573001234567",
                        "timestamp": "1",
                        "type": "text",
                        "text": {"body": "Hola"},
                    }],
                },
            }],
        }],
    }
    messages = parse_whatsapp_messages(payload)
    assert len(messages) == 1
    assert messages[0].text == "Hola"
    assert messages[0].contact_name == "Ana"
    assert messages[0].phone_number_id == "123"


def test_multimedia_is_ignored():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{
            "id": "wamid.2", "from": "57", "type": "image", "image": {"id": "abc"}
        }]}}]}],
    }
    assert parse_whatsapp_messages(payload) == []


def test_status_payload_is_ignored():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"statuses": [{"id": "x", "status": "sent"}]}}]}],
    }
    assert parse_whatsapp_messages(payload) == []
