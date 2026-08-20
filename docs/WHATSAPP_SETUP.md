# WhatsApp Cloud API

## Callback

```text
https://TU-DOMINIO/api/webhooks/whatsapp
```

## GET

Meta verificará el endpoint usando:

- `hub.mode`
- `hub.verify_token`
- `hub.challenge`

## POST

La V2 procesa únicamente eventos `messages` cuyo `type` sea `text`.

Eventos de status, imágenes, audio, documentos y video se reconocen como no procesables y se responde HTTP 200 sin ejecutar agentes.

## Variables

```env
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
META_GRAPH_API_VERSION=
META_APP_SECRET=
VERIFY_META_SIGNATURE=true
WHATSAPP_SEND_ENABLED=true
```

Para pruebas controladas puedes definir:

```env
WHATSAPP_ALLOWED_FROM_NUMBERS=573001234567
```
