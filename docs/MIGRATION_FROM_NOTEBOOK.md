# Mapeo notebook → V2

| Notebook | V2 |
|---|---|
| SQLite `db_connection()` | `database/connection.py` + Supabase |
| funciones SQL | `database/repository.py` |
| herramientas deterministas | `agents/tools.py` |
| `CLINIC_KNOWLEDGE` | `domain/knowledge.py` |
| contratos Pydantic | `domain/contracts.py` |
| `InMemorySaver` | `PostgresSaver` |
| supervisor/subgrafos | `agents/graph.py` |
| `invoke_revylia()` | `agents/runtime.py` |
| Langfuse | `observability/langfuse.py` |
| Telegram handler | `services/message_processor.py` + webhook WhatsApp |
| `update_id` temporal | `whatsapp_inbound_events.message_id` persistente |
| thread Telegram | `whatsapp:{wa_id}` → hash |

Voz y Telegram fueron removidos deliberadamente de esta entrega para reducir variables en la primera prueba de WhatsApp.
