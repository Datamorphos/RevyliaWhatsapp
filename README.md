# Revylia WhatsApp Multiagente — V2

Versión modular derivada del notebook de prueba de Revylia y preparada para una prueba vertical real mediante **WhatsApp Cloud API + FastAPI + LangGraph + Gemini + Supabase PostgreSQL + Langfuse**.

Esta V2 sustituye:

- `SQLite` → **Supabase PostgreSQL** para datos operativos.
- `InMemorySaver` → **PostgresSaver** para memoria conversacional persistente de LangGraph.
- Adaptador Telegram → **Webhook + cliente de WhatsApp Cloud API**.

Se mantienen las ideas centrales del notebook:

- Supervisor/orquestador.
- Subgrafo Recepción.
- Subgrafo Agenda.
- Subgrafo Recuperación.
- Subgrafo Clinic Brain.
- Máximo de dos especialistas por solicitud.
- Herramientas deterministas para escrituras y consultas.
- Guardas clínicas deterministas.
- `invoke_revylia(...)` como interfaz principal del AI Brain.
- `thread_id` hasheado por clínica y conversación.
- Observabilidad opcional con Langfuse y redacción de datos sensibles.

## Arquitectura de esta V2

```text
Usuario WhatsApp
      │
      ▼
WhatsApp Cloud API / Meta
      │
      ▼
POST /api/webhooks/whatsapp
      │
      ├── valida X-Hub-Signature-256 (opcional en dev)
      ├── procesa solo mensajes de texto
      ├── deduplicación persistente en Supabase
      │
      ▼
MessageProcessor
      │
      ▼
invoke_revylia(...)
      │
      ▼
Supervisor LangGraph
      │
 ┌────┼───────────────┬──────────────┐
 ▼    ▼               ▼              ▼
Recep Agenda        Recovery      Clinic Brain
 │      │               │              │
 └──────┴──────┬────────┴──────────────┘
               │
               ▼
      Supabase PostgreSQL
      ├── revylia.*        negocio
      └── checkpoints*     memoria LangGraph
               │
               ▼
          final_response
               │
               ▼
       WhatsApp Cloud API
               │
               ▼
            Usuario
```

## Lo que NO incluye todavía

Deliberadamente no se agregaron:

- voz/STT/TTS;
- imágenes/documentos;
- Redis;
- Celery/RQ;
- workers externos;
- campañas salientes automáticas;
- memoria semántica de largo plazo;
- RAG/vector database.

El objetivo de la V2 es validar primero el circuito **WhatsApp → múltiples agentes → herramientas → Supabase → WhatsApp**.

---

# 1. Requisitos

- Python 3.12 recomendado.
- Proyecto de Supabase.
- Aplicación de Meta con WhatsApp Cloud API.
- API key de Google AI para Gemini.
- Langfuse opcional.

---

# 2. Crear entorno local

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Instala:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Copia:

```bash
copy .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

---

# 3. Configurar Supabase

En **Supabase → Connect** obtén dos cadenas cuando sea posible:

### Runtime serverless

Usa **Transaction Pooler**, normalmente puerto `6543`:

```env
DATABASE_URL=postgresql://...
```

### Migraciones/setup

Usa preferiblemente Direct Connection o Session Pooler:

```env
DATABASE_URL_ADMIN=postgresql://...
```

Si estás haciendo una prueba y solo tienes una URL, `DATABASE_URL_ADMIN` puede omitirse y el script intentará usar `DATABASE_URL`.

Luego ejecuta:

```bash
python scripts/setup_database.py --seed
```

Este comando:

1. crea el esquema `revylia`;
2. crea las tablas operativas;
3. inserta datos demo idempotentes;
4. ejecuta `PostgresSaver.setup()`;
5. activa RLS sin políticas públicas sobre las tablas creadas para la prueba.

No ejecutes `setup()` desde cada webhook. Es una tarea de infraestructura que se realiza una vez por base de datos o cuando LangGraph requiera migraciones.

---

# 4. Configuración mínima para probar el Brain localmente

```env
REVYLIA_ENV=development
REVYLIA_CLINIC_ID=clinica-sonrisas
REVYLIA_MODEL=gemini-3.1-flash-lite
GOOGLE_API_KEY=...

DATABASE_URL=...
DATABASE_URL_ADMIN=...

REVYLIA_DISABLE_LANGFUSE=true
```

Prueba:

```bash
python scripts/test_agent_cli.py
```

Ejemplos:

```text
¿Cuánto cuesta una limpieza?
¿Qué disponibilidad tienen pasado mañana?
Quiero una cita para limpieza el 2026-08-24 a las 09:00. Soy Ana Pérez y mi número es 3001234567.
Quiero hablar con una persona.
```

---

# 5. Levantar FastAPI

```bash
uvicorn src.main:app --reload
```

Health:

```text
GET http://127.0.0.1:8000/api/health
```

Health DB:

```text
GET http://127.0.0.1:8000/api/health/database
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

# 6. Probar el webhook local sin Meta

Con la API encendida:

```bash
python scripts/send_test_event.py
```

El script simula un payload de WhatsApp.

Si:

```env
WHATSAPP_SEND_ENABLED=false
```

la respuesta se imprime en logs pero no se llama a Meta.

---

# 7. Configurar WhatsApp Cloud API

Variables:

```env
WHATSAPP_VERIFY_TOKEN=elige-un-token-largo
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
META_GRAPH_API_VERSION=...
META_APP_SECRET=...
VERIFY_META_SIGNATURE=true
WHATSAPP_SEND_ENABLED=true
```

Para una primera verificación del endpoint puedes dejar temporalmente:

```env
VERIFY_META_SIGNATURE=false
```

pero actívalo para una prueba más real.

Callback URL:

```text
https://TU-DOMINIO.vercel.app/api/webhooks/whatsapp
```

Verify token:

```text
el mismo valor de WHATSAPP_VERIFY_TOKEN
```

El webhook `GET` implementa el challenge de Meta y el `POST` procesa mensajes entrantes de texto.

---

# 8. Desplegar en Vercel

El entry point es:

```text
api/index.py
```

Sube el repositorio a GitHub e impórtalo en Vercel.

Configura en Vercel todas las variables del `.env` necesarias. Nunca subas `.env` al repositorio.

El runtime usa conexiones cortas hacia Supabase y desactiva prepared statements (`prepare_threshold=None`) para ser compatible con transaction pooling.

---

# 9. Memoria multi-turn

WhatsApp usa:

```python
thread_id = f"whatsapp:{wa_id}"
```

`invoke_revylia()` transforma ese valor con SHA-256 junto al `tenant_id` antes de entregarlo a LangGraph.

Por tanto:

```text
WhatsApp 573001234567
        │
        ▼
whatsapp:573001234567
        │
        ▼
stable_hash(tenant + thread)
        │
        ▼
PostgresSaver / Supabase
```

La conversación no depende de que dos requests caigan en la misma instancia de Vercel.

---

# 10. Tablas operativas

La migración crea:

```text
revylia.clinics
revylia.patients
revylia.appointments
revylia.opportunities
revylia.escalations
revylia.recovery_messages
revylia.whatsapp_inbound_events
```

Además LangGraph crea sus tablas de checkpoints en PostgreSQL.

Todas las tablas de negocio incluyen `clinic_id` para no repetir la limitación del notebook, donde las herramientas SQLite no filtraban realmente por tenant.

---

# 11. Idempotencia de WhatsApp

Meta puede reenviar un webhook. Antes de invocar los agentes se intenta insertar el `message_id` en:

```text
revylia.whatsapp_inbound_events
```

La clave primaria evita ejecutar dos veces el mismo mensaje en una prueba normal.

Esta V2 implementa **idempotencia de entrada**, no exactamente-once distribuido. Cuando agregues colas/workers conviene evolucionar a una máquina de estados/reintentos más robusta.

---

# 12. Langfuse

Para activarlo:

```env
REVYLIA_DISABLE_LANGFUSE=false
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
REVYLIA_TRACE_CONTENT_MODE=masked
REVYLIA_TRACE_SAMPLING_RATE=1.0
```

El canal aparecerá como:

```text
channel:whatsapp
```

Se preservan hashes para tenant/conversación y se enmascaran teléfonos, correos e identificadores en trazas.

---

# 13. Flujo recomendado de prueba

### Prueba A — Clinic Brain

```text
¿Cuánto cuesta una limpieza?
```

Esperado:

```text
Supervisor → Clinic Brain → WhatsApp
```

### Prueba B — Agenda consulta

```text
¿Qué disponibilidad tienen el 2026-08-24?
```

Esperado:

```text
Supervisor → Agenda → Supabase → WhatsApp
```

### Prueba C — conversación multi-turn

```text
Quiero una limpieza.
```

Luego:

```text
El lunes.
```

Luego:

```text
A las 10. Soy Ana Pérez, 3001234567.
```

Aquí validas PostgresSaver.

### Prueba D — acción real

Después de confirmar una cita:

```bash
python scripts/inspect_database.py appointments
```

La fila debe existir en Supabase.

---

# 14. Próxima evolución después de validar esta V2

Cuando este circuito esté estable, la siguiente arquitectura es:

```text
Webhook
  ↓
Queue
  ↓
Worker LangGraph
  ↓
Supabase
  ↓
WhatsApp
```

En ese momento sí tiene sentido añadir Redis/cola, retries, dead-letter queue, rate limits por clínica y procesamiento asíncrono.
