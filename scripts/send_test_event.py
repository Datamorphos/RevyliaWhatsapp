import json
import uuid

import httpx


PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "TEST_WABA_ID",
            "changes": [
                {
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15550000000",
                            "phone_number_id": "TEST_PHONE_NUMBER_ID",
                        },
                        "contacts": [
                            {
                                "profile": {"name": "Usuario Prueba"},
                                "wa_id": "573001234567",
                            }
                        ],
                        "messages": [
                            {
                                "from": "573001234567",
                                "id": "wamid.TEST." + uuid.uuid4().hex,
                                "timestamp": "1700000000",
                                "type": "text",
                                "text": {"body": "¿Cuánto cuesta una limpieza?"},
                            }
                        ],
                    },
                }
            ],
        }
    ],
}


def main():
    response = httpx.post(
        "http://127.0.0.1:8000/api/webhooks/whatsapp",
        json=PAYLOAD,
        timeout=60,
    )
    print("STATUS:", response.status_code)
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(response.text)


if __name__ == "__main__":
    main()
