# Especificación técnica — Panel Web Revylia con CopilotKit

> Documento autónomo. No asume acceso a ninguna conversación previa, plan de sesión ni
> agentes que lo hayan producido. Todo lo afirmado aquí como "verificado" fue leído
> directamente del código en `C:\Users\Windows\RevyliaWhatsapp`, rama `feat/panel-web`,
> el 2026-09-12. Todo lo marcado como "pendiente de verificar" NO fue comprobado en esta
> sesión (no hubo base de datos desplegada ni proyecto Supabase real disponible).
>
> Convención de este documento: **[EXISTENTE]** = ya está en el repositorio y funciona
> hoy. **[NUEVO]** = hay que construirlo; no existe todavía. **[LIMITACIÓN VERIFICADA]** =
> comprobado en el código, es una restricción real de los datos o del sistema, no una
> opinión. **[PENDIENTE DE VERIFICAR]** = no se pudo comprobar en esta sesión.

---

## Índice

0. Resumen ejecutivo y honestidad del entregable
1. Contexto de Revylia y stack actual
2. Flujo actual: WhatsApp → supervisor → especialistas
3. Diccionario completo de datos (`revylia.*` y checkpoints)
4. Limitaciones verificadas en el repositorio
5. Arquitectura de la nueva app (panel + copiloto)
6. Seguridad: identidad, `clinic_id`, credencial de solo lectura, RLS
7. Contratos de consulta — API del panel (`GET /api/v1/...`)
8. Contrato del copiloto (agente LangGraph de solo lectura)
9. Contrato de componentes de UI
10. Configuración por componente (valores ficticios)
11. Despliegue — estado real y deuda técnica conocida
12. Secuencia de implementación
13. Pruebas de aceptación
14. Qué quedó sin verificar en esta sesión

---

## 0. Resumen ejecutivo y honestidad del entregable

Se va a construir un panel web interno, de **solo lectura en su totalidad** (API,
copiloto y credencial de base de datos), para que el personal de **una sola clínica**
consulte los datos que hoy genera el gateway de WhatsApp de Revylia: resumen operativo,
agenda, pacientes, oportunidades, escalaciones, recuperación de pacientes inactivos y
monitor de eventos de WhatsApp. Incluye un copiloto lateral (CopilotKit + AG-UI +
LangGraph) que consulta esos mismos datos en lenguaje natural, nunca escribe, y siempre
cita fuente, filtros y momento de generación.

Dos hechos deben quedar explícitos desde el resumen porque cambian cómo se implementa lo
que sigue de este documento — no son detalles menores enterrados en una sección tardía:

1. **RLS está activado sin políticas en las 7 tablas `revylia.*`.** El gateway actual
   funciona porque conecta con el rol dueño de las tablas (los dueños de tabla omiten RLS
   en PostgreSQL). Un rol nuevo de solo lectura con `GRANT SELECT` **no verá ninguna fila
   y no recibirá ningún error** — la consulta será válida y devolverá cero resultados.
   Esto no es un bug a corregir en el código del panel; es una migración de base de datos
   pendiente (`migrations/003_panel_readonly.sql`, ver §11) que debe ejecutar una persona
   con credenciales de administrador, no un agente ni el proceso de build.
2. **La separación de despliegue del gateway respecto del panel NO se logró.** El plan
   original pedía que el panel (API + copiloto) se desplegara por separado del webhook de
   WhatsApp. En el estado real de este repositorio, `src/main.py` monta un único
   `FastAPI()` y `pyproject.toml` declara un único entry point para Vercel
   (`[tool.vercel] entrypoint = "src.main:app"`). Cualquier router de panel que se
   incluya en esa misma `app` queda en el mismo proceso y el mismo despliegue que el
   webhook. Esto se documenta como **deuda técnica conocida**, no como logro. §11 explica
   por qué y cómo separarlo después.

---

## 1. Contexto de Revylia y stack actual [EXISTENTE]

Revylia es un gateway de WhatsApp con un backend multiagente (LangGraph) para una
clínica. El proyecto se llama internamente `revylia-whatsapp-multiagent-v2`
(`pyproject.toml`, versión de proyecto `0.2.0`).

### 1.1 Versiones declaradas realmente en `pyproject.toml`

No inventadas — copiadas literalmente del archivo:

```toml
requires-python = ">=3.12"

fastapi>=0.128,<1
httpx>=0.28,<1
pydantic==2.13.4
pydantic-settings>=2.11,<3
langgraph==1.2.9
langgraph-checkpoint-postgres>=3.0.5,<4
langchain==1.3.14
langchain-google-genai==4.2.7
psycopg[binary]>=3.2,<4
psycopg-pool>=3.2,<4
langfuse==4.14.1

# [project.optional-dependencies] panel  (ya instalado, no lo agrega ningún agente)
pyjwt[crypto]>=2.14,<3
ag-ui-langgraph>=0.0.45,<0.1
copilotkit>=0.1.96,<0.2

# [project.optional-dependencies] dev
uvicorn[standard]>=0.34,<1
pytest>=8,<10
pytest-asyncio>=0.24,<2
```

Punto importante para quien construya el panel: **el extra `panel` ya está declarado en
`pyproject.toml`** con `pyjwt[crypto]`, `ag-ui-langgraph` y `copilotkit`. Esto es estado
ya existente, observado en el repo — no hay que instalarlo ni agregarlo; solo activarlo
(`pip install -e ".[panel]"` o equivalente en el entorno de despliegue).

### 1.2 Papel de cada componente

| Componente | Rol en Revylia hoy |
|---|---|
| **FastAPI** | Expone el webhook de WhatsApp y dos endpoints de salud (`src/main.py`). No expone ninguna API de datos todavía. |
| **Pydantic 2** | Modelos de mensajes entrantes, configuración (`Settings`) y esquemas estructurados de salida de los agentes (decisiones de supervisor/especialistas). |
| **LangGraph** | Orquesta el supervisor y 4 subgrafos de especialistas (recepción, agenda, recuperación, clinic brain) con checkpointing en PostgreSQL. |
| **LangChain + langchain-google-genai** | Capa de invocación de modelos Gemini con salida estructurada para cada nodo del grafo. |
| **Gemini** (`REVYLIA_MODEL`, por defecto `gemini-3.1-flash-lite`) | Modelo de lenguaje usado por todos los nodos LLM del grafo. |
| **psycopg 3 (+ pool)** | Driver de conexión a PostgreSQL, en modo `dict_row`, `prepare_threshold=None` (requerido por el Transaction Pooler de Supabase, ver `src/database/connection.py`). |
| **Supabase PostgreSQL** | Base de datos operativa (schema `revylia`) y almacén de checkpoints de LangGraph (schema `public`). |
| **PostgresSaver** (`langgraph-checkpoint-postgres`) | Persiste el estado conversacional de WhatsApp por `thread_id` hasheado. Sus tablas viven en `public`, **no en `revylia`**. |
| **WhatsApp Cloud API** | Canal de entrada/salida de mensajes; verificación de webhook, firma `X-Hub-Signature-256` opcional, envío de respuestas. |
| **Langfuse** | Observabilidad opcional (`REVYLIA_DISABLE_LANGFUSE=true` por defecto); enmascara datos sensibles en las trazas. |
| **Vercel** | Plataforma de despliegue; `[tool.vercel] entrypoint = "src.main:app"` apunta a la única app FastAPI del repo. |

### 1.3 Stack del frontend ya scaffoldeado [EXISTENTE — scaffold sin funcionalidad de panel]

El directorio `web/` ya existe con un proyecto Next.js inicializado (no construido por
este documento). De `web/package.json`, versiones reales:

```json
"next": "16.3.5",
"react": "19.2.8",
"react-dom": "19.2.8",
"@copilotkit/react-core": "^1.71.1",
"@copilotkit/react-ui": "^1.71.1",
"@copilotkit/runtime": "^1.71.1",
"@ag-ui/client": "^0.0.59",
"@supabase/ssr": "^0.12.7",
"@supabase/supabase-js": "^2.116.0",
"@tanstack/react-table": "^9.2.4",
"date-fns": "^4.4.0",
"tailwindcss": "^4",
"shadcn": "^4.21.0"
```

`packageManager: pnpm@10.33.2`. Ya hay primitivos de shadcn/ui generados en
`web/components/ui/` (button, card, table, badge, input, select, dropdown-menu, avatar,
separator, skeleton, tabs, tooltip, popover, scroll-area, sonner, alert, breadcrumb,
label, textarea, sheet, dialog, chart, input-group, sidebar, command). El panel se
construye **sobre** estos primitivos; no se reinstala nada (contrato §0.6: ningún agente
ejecuta instalaciones).

**[PENDIENTE DE VERIFICAR]** El contrato congelado del proyecto (`docs/CONTRACT_PANEL.md`
§6) exige usar `@copilotkit/runtime/v2` con `CopilotRuntime` + `createCopilotRuntimeHandler`
(`mode: "single-route"`), generación v2 en ambos lados, sin mezclar con `remoteEndpoints`
v1. `package.json` fija `@copilotkit/runtime` en `^1.71.1`. No se verificó en esta sesión
si esa versión de paquete expone el subpath `/v2` con esa API exacta — se instaló sin
ejecutar el proyecto. Antes de escribir `web/app/api/copilotkit/route.ts`, quien lo
implemente debe confirmar contra la documentación de esa versión instalada (Context7 o el
propio paquete en `node_modules`) que el patrón v2 existe tal cual el contrato lo describe.

---

## 2. Flujo actual: WhatsApp → supervisor → especialistas [EXISTENTE]

```text
Usuario WhatsApp
      │
      ▼
WhatsApp Cloud API / Meta
      │
      ▼
GET/POST /api/webhooks/whatsapp        (src/webhooks/whatsapp.py)
      │  GET  → responde el "hub.challenge" de verificación de Meta
      │  POST → valida X-Hub-Signature-256 (si VERIFY_META_SIGNATURE=true)
      │         parsea mensajes de texto (src/integrations/whatsapp/parser.py)
      ▼
MessageProcessor.process()             (src/services/message_processor.py)
      │  1. filtra por allowlist de números (si está configurada)
      │  2. rechaza mensajes > REVYLIA_MAX_INPUT_CHARS
      │  3. deduplica: INSERT ... ON CONFLICT DO NOTHING en
      │     revylia.whatsapp_inbound_events (WhatsAppEventRepository.claim)
      │     → si ya existía el message_id, se ignora como duplicado
      ▼
invoke_revylia(...)                    (src/agents/runtime.py)
      │  calcula thread_id = SHA-256(tenant_id + "whatsapp:<wa_id>")[:24]
      │  abre PostgresSaver sobre una conexión de checkpoint (autocommit)
      ▼
Grafo LangGraph (src/agents/graph.py)
      │
      ▼
  supervisor_node
      │  decide qué especialistas ejecutar (máx. REVYLIA_MAX_AGENT_STEPS, def. 2)
      │  con fallback determinista por palabras clave si el LLM del router falla
      │
      ├──▶ reception_subgraph    (saludo, calificación de oportunidad, escalación,
      │                           guardas de riesgo clínico)
      ├──▶ agenda_subgraph       (consultar disponibilidad, crear o reprogramar citas)
      ├──▶ recovery_subgraph     (listar pacientes recuperables, borradores de mensaje)
      └──▶ clinic_brain_subgraph (responde con CLINIC_KNOWLEDGE, sin escribir nada)
      │
      ▼
  finalizer_node → agrupa resultados en una sola respuesta en español
      │
      ▼
MessageProcessor envía la respuesta por WhatsApp Cloud API
      │
      ▼
WhatsAppEventRepository.mark_completed / mark_failed
      (actualiza revylia.whatsapp_inbound_events)
```

### 2.1 Por qué `invoke_revylia()` NO puede ser el agente del panel [VERIFICADO]

`invoke_revylia()` (`src/agents/runtime.py:242`) invoca el mismo grafo completo que usa
WhatsApp. Ese grafo, a través de `ClinicTools` (`src/agents/tools.py`) y
`ClinicRepository` (`src/database/repository.py`), puede ejecutar escrituras reales:

- `agenda_subgraph` → `create_appointment`, `reschedule_appointment` (INSERT/UPDATE en
  `revylia.appointments`, y de paso `get_or_create_patient`, que puede **crear un
  paciente nuevo**).
- `reception_subgraph` → `create_opportunity`, `create_escalation` (INSERT en
  `revylia.opportunities` / `revylia.escalations`).
- `recovery_subgraph` → `save_recovery_message` (INSERT en `revylia.recovery_messages`).

No existe ningún parámetro de `invoke_revylia()` que desactive estas escrituras: son
parte del comportamiento normal de los especialistas cuando el usuario pide agendar,
reportar una queja o solicitar recuperación. Por eso el copiloto del panel **no reutiliza
este grafo ni sus herramientas**: necesita un grafo nuevo, separado, con herramientas de
solo lectura explícitamente distintas (ver §8). Esto es una decisión de diseño obligatoria,
no una preferencia de estilo.

---

## 3. Diccionario completo de datos [EXISTENTE — leído de `migrations/001_business.sql`]

Fuente: `migrations/001_business.sql` (idéntico en contenido, salvo terminador de línea,
a la copia suelta en la raíz del repo `001_business.sql`; esta última es un archivo sin
seguimiento de git — no representa una versión distinta del esquema, ver §14). Semillas
demo: `migrations/002_seed_demo.sql`.

Las 7 tablas viven en el **schema `revylia`**. Los checkpoints de LangGraph (PostgresSaver)
viven en el **schema `public`** y se describen aparte en §3.2: son un sistema de memoria
conversacional de infraestructura, no datos de negocio, y el panel no debe tocarlos.

### 3.1 Tablas operativas (`revylia.*`)

#### `revylia.clinics`

| Campo | Tipo | Nulable | Default | Notas |
|---|---|---|---|---|
| `id` | `TEXT` | NO (PK) | — | Identificador de clínica, p. ej. `clinica-sonrisas`. Es la misma cadena que `REVYLIA_CLINIC_ID`. |
| `name` | `TEXT` | NO | — | |
| `timezone` | `TEXT` | NO | `'America/Bogota'` | **Nota de divergencia:** existe esta columna, pero `src/database/repository.py` **hardcodea** `BOGOTA_TZ = ZoneInfo("America/Bogota")` en Python y no lee esta columna. El panel debe decidir cuál usar como fuente de verdad (ver §6.5); por defecto se recomienda seguir usando `America/Bogota` como valor inicial, igual que hoy, hasta que se decida leer la columna. |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

Sin índices adicionales declarados (PK ya indexa `id`).

#### `revylia.patients`

| Campo | Tipo | Nulable | Default | Notas |
|---|---|---|---|---|
| `id` | `BIGSERIAL` | NO (PK) | autoincremental | Serializar como `string` en JSON. |
| `clinic_id` | `TEXT` | NO (FK → `clinics.id`, `ON DELETE CASCADE`) | — | |
| `name` | `TEXT` | NO | — | Sin unicidad: **pueden existir homónimos** (dos pacientes con el mismo `name`). |
| `phone` | `TEXT` | SÍ | — | `UNIQUE (clinic_id, phone)` — pero PostgreSQL no compara `NULL` como igual a sí mismo, así que **puede haber varios pacientes con `phone IS NULL`** en la misma clínica. |
| `last_visit_date` | `DATE` | SÍ | — | |
| `last_service` | `TEXT` | SÍ | — | Texto libre; no hay FK a ninguna tabla de servicios (no existe tabla de catálogo, ver §4). |
| `status` | `TEXT` | NO | `'active'` | `CHECK (status IN ('active','inactive'))` — **enum aplicado en BD.** |
| `consent_marketing` | `BOOLEAN` | NO | `false` | |
| `notes` | `TEXT` | SÍ | — | **Texto libre no confiable** (ver §6.6): puede contener contenido escrito por el flujo conversacional. |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

Índice: `idx_revylia_patients_clinic_status (clinic_id, status)`.

#### `revylia.appointments`

| Campo | Tipo | Nulable | Default | Notas |
|---|---|---|---|---|
| `id` | `BIGSERIAL` | NO (PK) | autoincremental | |
| `clinic_id` | `TEXT` | NO (FK → `clinics.id`, CASCADE) | — | |
| `patient_id` | `BIGINT` | **NO** (FK → `patients.id`, `ON DELETE RESTRICT`) | — | Siempre hay paciente asociado; nunca es `NULL`. |
| `service` | `TEXT` | NO | — | Texto libre, **sin FK ni CHECK contra ningún catálogo**. El seed demo inserta `'Ortodoncia - control'`, que **no existe** en `CLINIC_KNOWLEDGE.services` (que solo define `Valoración general`, `Limpieza dental`, `Blanqueamiento`, `Ortodoncia - valoración`) — evidencia directa de que no hay catálogo real ni consistencia garantizada entre lo agendado y lo publicitado. |
| `appointment_date` | `DATE` | NO | — | Fecha civil, sin zona horaria. |
| `appointment_time` | `TIME` | NO | — | Hora en punto en la práctica (ver §4), sin zona horaria. |
| `status` | `TEXT` | NO | `'confirmed'` | `CHECK (status IN ('pending','confirmed','cancelled','completed'))` — **enum aplicado en BD.** |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NO | `now()` | Se actualiza manualmente en `reschedule_appointment`, no hay trigger automático. |

Índices: `idx_revylia_appointments_clinic_date (clinic_id, appointment_date)`; además
`idx_revylia_appointment_slot` — **único**, parcial —
`ON (clinic_id, appointment_date, appointment_time) WHERE status IN ('confirmed','pending')`.
Este índice es el que garantiza "un único cupo por clínica/fecha/hora" (ver §4): dos citas
`confirmed`/`pending` no pueden compartir clínica+fecha+hora; una `cancelled` sí libera el
cupo para una nueva inserción.

#### `revylia.opportunities`

| Campo | Tipo | Nulable | Default | Notas |
|---|---|---|---|---|
| `id` | `BIGSERIAL` | NO (PK) | autoincremental | |
| `clinic_id` | `TEXT` | NO (FK, CASCADE) | — | |
| `patient_id` | `BIGINT` | **SÍ** (FK → `patients.id`, `ON DELETE SET NULL`) | — | Puede ser `NULL` cuando el flujo de recepción no logró identificar al paciente. |
| `patient_name` | `TEXT` | SÍ | — | Copia denormalizada del nombre reportado en la conversación; **puede diferir** del `name` real en `patients` (o puede ser el único dato disponible cuando `patient_id IS NULL`). |
| `phone` | `TEXT` | SÍ | — | Copia denormalizada, normalizada a solo dígitos (`normalize_phone`). |
| `reason` | `TEXT` | NO | — | **Texto libre no confiable** (ver §6.6). |
| `score` | `INTEGER` | NO | `50` | `CHECK (score BETWEEN 0 AND 100)`. |
| `status` | `TEXT` | NO | `'open'` | **Sin `CHECK` en la base de datos.** El valor `'open'` es una convención de la aplicación (`repository.py`), no un enum aplicado por PostgreSQL. El endpoint `/opportunities` filtra por `status` como texto libre. |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

Sin índice propio más allá de la PK (los filtros de listado dependerán de `clinic_id` +
`status`/`score`, sin índice compuesto dedicado — candidato de optimización, no bloqueante).

#### `revylia.escalations`

| Campo | Tipo | Nulable | Default | Notas |
|---|---|---|---|---|
| `id` | `BIGSERIAL` | NO (PK) | autoincremental | |
| `clinic_id` | `TEXT` | NO (FK, CASCADE) | — | |
| `patient_id` | `BIGINT` | **SÍ** (FK, `ON DELETE SET NULL`) | — | Puede ser `NULL`. |
| `reason` | `TEXT` | NO | — | **Texto libre no confiable.** |
| `priority` | `TEXT` | NO | — (obligatorio, sin default) | `CHECK (priority IN ('low','medium','high','urgent'))` — **enum aplicado en BD.** |
| `status` | `TEXT` | NO | `'pending'` | **Sin `CHECK`.** Convención de aplicación, igual que en `opportunities`. |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

Sin índice propio más allá de la PK.

#### `revylia.recovery_messages`

| Campo | Tipo | Nulable | Default | Notas |
|---|---|---|---|---|
| `id` | `BIGSERIAL` | NO (PK) | autoincremental | |
| `clinic_id` | `TEXT` | NO (FK, CASCADE) | — | |
| `patient_id` | `BIGINT` | **NO** (FK → `patients.id`, `ON DELETE CASCADE`) | — | Siempre hay paciente asociado. |
| `message` | `TEXT` | NO | — | **Texto libre no confiable**, generado por LLM en el flujo de WhatsApp. |
| `approval_required` | `BOOLEAN` | NO | `true` | En la V2 del gateway, `ClinicTools.save_recovery_message` fuerza este valor a `true` siempre, sin excepción. |
| `status` | `TEXT` | NO | `'draft'` | **Sin `CHECK`.** Valores usados por la aplicación: `'draft'` o `'approved'` (`repository.py`), pero PostgreSQL no impide otro valor. |
| `created_at` | `TIMESTAMPTZ` | NO | `now()` | |

Sin índice propio más allá de la PK.

#### `revylia.whatsapp_inbound_events`

| Campo | Tipo | Nulable | Default | Notas |
|---|---|---|---|---|
| `id` | `BIGSERIAL` | NO (`UNIQUE`, no es la PK) | autoincremental | Existe como columna secundaria para poder construir un cursor `(received_at, id)` estable (ver §7.5). |
| `message_id` | `TEXT` | NO (**PK**) | — | Id de mensaje de WhatsApp Cloud API; es la clave de idempotencia (`ON CONFLICT (message_id) DO NOTHING`). |
| `clinic_id` | `TEXT` | NO (FK, CASCADE) | — | |
| `from_number_hash` | `TEXT` | NO | — | `SHA-256(número crudo)[:24]` vía `stable_hash()`. **No se expone en la API del panel** (contrato §5.5). |
| `status` | `TEXT` | NO | `'processing'` | `CHECK (status IN ('processing','completed','failed'))` — **enum aplicado en BD.** |
| `response_text` | `TEXT` | SÍ | — | La respuesta final que Revylia envió al paciente. **El texto que el paciente escribió NUNCA se persiste** — solo se guarda la respuesta de Revylia, no el mensaje entrante. |
| `error_type` | `TEXT` | SÍ | — | Nombre de clase de excepción, truncado a 120 caracteres. |
| `received_at` | `TIMESTAMPTZ` | NO | `now()` | |
| `processed_at` | `TIMESTAMPTZ` | SÍ | — | |

Índice: `idx_revylia_events_clinic_received (clinic_id, received_at DESC)`. **No cubre**
el orden exacto de paginación por keyset del contrato (`received_at, id`) — ver §7.5,
nota de optimización.

### 3.2 Checkpoints de LangGraph (`public.*`) — separados de los datos operativos

`scripts/setup_database.py::setup_checkpoints()` ejecuta `PostgresSaver.setup()`, que crea
en el **schema `public`** (no `revylia`):

```text
public.checkpoint_migrations
public.checkpoints
public.checkpoint_blobs
public.checkpoint_writes
```

El mismo script activa `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` sobre esas 4 tablas,
también **sin políticas**. Estas tablas contienen el estado serializado de las
conversaciones de WhatsApp (mensajes, resultados intermedios del grafo) indexado por
`thread_id` hasheado — es memoria de infraestructura de LangGraph, no una tabla de negocio
de la clínica.

**[PENDIENTE DE VERIFICAR]** El esquema de columnas interno de estas 4 tablas no está en
este repositorio (lo define la librería `langgraph-checkpoint-postgres` en tiempo de
ejecución). No se verificó su estructura exacta en esta sesión.

Consecuencias para el panel, ambas obligatorias:

1. El copiloto y la API del panel **no deben leer ni escribir** estas tablas bajo ningún
   concepto (contrato §0.5: sin checkpointer en el agente del panel).
2. El rol de solo lectura que se cree para el panel (§6.3) **no debe recibir ningún
   `GRANT`** sobre el schema `public` ni sobre estas tablas. Si en algún momento alguien
   necesita depurar el estado conversacional de WhatsApp, eso se hace con la credencial
   administrativa existente, nunca con la del panel.

### 3.3 Relaciones (resumen)

```text
clinics (1) ──< patients (N)
patients (1) ──< appointments (N)         [patient_id NOT NULL]
patients (1) ──< recovery_messages (N)    [patient_id NOT NULL]
patients (0..1) ──< opportunities (N)     [patient_id NULLABLE, SET NULL]
patients (0..1) ──< escalations (N)       [patient_id NULLABLE, SET NULL]
clinics (1) ──< whatsapp_inbound_events (N)   [SIN relación a patients]
```

No existe ninguna clave foránea entre `whatsapp_inbound_events` y `patients`: solo se
guarda el hash del número, y ese hash no es recomputable de forma útil en la práctica.
`WhatsAppEventRepository.claim()` recibe `message.from_number` — el `wa_id` crudo tal
como lo entrega Meta, con prefijo de país y sin separadores (el propio `README.md` usa el
ejemplo `573001234567`) — y le aplica `stable_hash()` sin normalizar. En cambio,
`patients.phone` se guarda vía `normalize_phone()` con el valor que el paciente escribió
en la conversación, que en la práctica observada (datos demo y ejemplos del propio
`README.md`, p. ej. `3001234567`/`3001112233`) es un número local de 10 dígitos, **sin**
el prefijo de país. `normalize_phone()` solo elimina caracteres no numéricos; no agrega ni
retira el prefijo de país. Por lo tanto, recomputar `stable_hash()` sobre el valor
guardado en `patients.phone` no reproduce el hash almacenado en
`whatsapp_inbound_events.from_number_hash` — son cadenas de entrada distintas por
construcción, no solo "sin garantía" de coincidir. Esto confirma, con evidencia de código
y no solo de esquema, que **no existe ruta de correlación evento→paciente**, ni siquiera
recomputando el hash manualmente.

---

## 4. Limitaciones verificadas en el repositorio

Cada punto siguiente fue comprobado leyendo código o migraciones reales, no supuesto.
Cada uno tiene un número de subsección explícito porque se cita desde otras partes del
documento (§7, §12, §13).

### 4.1 No existe API de panel

`src/main.py` solo registra `whatsapp_router` (prefijo `/api`) y dos endpoints de salud
(`/api/health`, `/api/health/database`). No hay ningún router de datos de negocio.

### 4.2 Los eventos de WhatsApp no permiten reconstruir un historial ni vincularse a un paciente

`whatsapp_inbound_events` solo persiste `from_number_hash` (irreversible) y
`response_text` (la respuesta de Revylia, nunca el mensaje entrante del paciente). No hay
FK a `patients`. El módulo de eventos del panel debe presentarse explícitamente como
"estado de procesamiento", nunca como "hilo de conversación".

### 4.3 No hay tablas de catálogo de servicios/precios/duración/reglas

Todo eso vive en `CLINIC_KNOWLEDGE` (`src/domain/knowledge.py`), un diccionario Python
embebido en el código, con 4 servicios, horarios de atención declarados como texto y una
lista de reglas de negocio. `appointments.service` es `TEXT` libre sin FK ni CHECK — de
hecho el dato demo (`'Ortodoncia - control'`) ni siquiera coincide con ninguna clave de
`CLINIC_KNOWLEDGE.services` (que solo tiene `Ortodoncia - valoración`), lo cual es
evidencia directa, no solo teórica, de la ausencia de catálogo relacional.

### 4.4 La agenda modela franjas de una hora y un único cupo por clínica/fecha/hora

No modela profesionales, consultorios ni duración real.
`ClinicRepository.list_available_slots` (`src/database/repository.py:92-119`) genera
candidatos así:

- Domingo (`date.weekday() == 6`) → `[]` (cerrado).
- Sábado (`weekday() == 5`) → horas `range(8, 12)` → slots exactos
  `08:00, 09:00, 10:00, 11:00`.
- Resto de días → horas `range(8, 17)` → slots exactos
  `08:00, 09:00, ..., 16:00` (**16:00, no 17:00** — `range(8,17)` es exclusivo del
  límite superior; el horario "08:00-17:00" publicado en `CLINIC_KNOWLEDGE` es solo la
  ventana de atención, el último slot reservable es 16:00).
- `duration_minutes` de `CLINIC_KNOWLEDGE` **nunca se lee** en esta función: cada slot
  ocupa exactamente 1 hora en el modelo de datos, sin importar cuánto dure el servicio
  realmente.
- "Ocupado" = existe una fila en `appointments` con esa `clinic_id`+`appointment_date`+
  `appointment_time` y `status IN ('confirmed','pending')` — reforzado por el índice
  único parcial `idx_revylia_appointment_slot`.

No hay ninguna noción de profesional, consultorio, sala ni de agenda paralela: un solo
cupo por hora por clínica, punto.

### 4.5 No hay datos suficientes para facturación, ingresos reales ni conversión atribuida

No existe tabla de pagos, facturas ni transacciones. `opportunities.score` es un valor
heurístico (0-100) generado por el LLM de recepción, no una medición de conversión real
ni de ingreso. `CLINIC_KNOWLEDGE.services[...].price_cop` es informativo y puede no
coincidir con lo que realmente se cobra (así lo dice la propia regla de negocio: "Los
precios son informativos y pueden cambiar después de una valoración").

### 4.6 Los datos demo no representan la configuración real de la clínica

`002_seed_demo.sql` inserta una sola clínica ficticia (`clinica-sonrisas`) con 5
pacientes y 1 cita. El nombre de servicio insertado en la cita demo
(`'Ortodoncia - control'`) ni siquiera existe en el catálogo informativo
`CLINIC_KNOWLEDGE`, lo que demuestra en la práctica que ambos "catálogos" (el operativo
en `appointments.service` y el informativo en `CLINIC_KNOWLEDGE`) pueden divergir
libremente porque nada en el esquema los mantiene sincronizados.

### 4.7 `status` no es un enum garantizado por PostgreSQL en todas las tablas

Solo `patients.status`, `appointments.status` y `whatsapp_inbound_events.status` tienen
`CHECK`. `opportunities.status`, `escalations.status` y `recovery_messages.status` son
`TEXT` libre — su dominio de valores (`open`, `pending`, `draft`, `approved`, etc.) es
una convención de `src/database/repository.py`, no una garantía de la base de datos.
Cualquier consulta o KPI que filtre por estos campos debe documentar que el filtro
depende de una convención de aplicación, no de un dominio cerrado por esquema.

---

## 5. Arquitectura de la nueva app

### 5.1 Vista de bloques [NUEVO, salvo lo ya marcado EXISTENTE]

```text
Personal de la clínica
        │  navegador (escritorio o móvil)
        ▼
┌───────────────────────────────────────────────────────────┐
│  Next.js App Router + TypeScript + Tailwind      [NUEVO]   │
│                                                              │
│  ┌────────────────┐   ┌───────────────────────────────┐    │
│  │ Supabase Auth   │   │ Copilot Runtime (v2)           │    │
│  │ (login, sesión) │   │ /app/api/copilotkit/route.ts  │    │
│  └────────┬────────┘   └───────────────┬────────────────┘    │
│           │                            │  AG-UI (HttpAgent)  │
│  ┌────────▼────────────────────┐       │                      │
│  │ Módulos del panel            │       │                      │
│  │ resumen · agenda · pacientes │       │                      │
│  │ oportunidades · escalaciones │       │                      │
│  │ recuperación · eventos       │       │                      │
│  │  lib/api/client.ts           │       │                      │
│  └────────┬────────────────────┘       │                      │
└───────────┼────────────────────────────┼──────────────────────┘
            │ Bearer <access_token>       │ AG-UI stream
            ▼                            ▼
┌───────────────────────┐      ┌─────────────────────────────────┐
│ FastAPI panel API      │      │ Agente LangGraph de solo lectura │
│ src/panel/**  [NUEVO]  │      │ src/panel_agent/**   [NUEVO]      │
│ GET /api/v1/...        │      │ "revylia_panel"                   │
│ - valida JWT (JWKS)    │      │ - Gemini (REVYLIA_MODEL)          │
│ - fija clinic_id       │      │ - sin checkpointer                │
│ - NO usa ClinicRepo    │      │ - herramientas = §7, mismas       │
└───────────┬────────────┘      │   funciones de src/panel/queries.py│
            │                    └───────────────┬────────────────────┘
            │  src/panel/queries.py + db.py       │
            │  (capa compartida, solo SELECT)      │
            └───────────────────┬───────────────────┘
                                 ▼
                    Credencial PostgreSQL de SOLO LECTURA
                    (PANEL_DATABASE_URL, rol propio)
                                 ▼
                    Supabase PostgreSQL — schema revylia
                    (RLS + políticas FOR SELECT, ver §6.4)
```

Puntos de diseño que se derivan directamente del contrato congelado
(`docs/CONTRACT_PANEL.md`) y deben respetarse:

- **`src/panel/` nunca importa `ClinicRepository`.** Esa clase tiene métodos de
  escritura y un `read_table()` que interpola el nombre de tabla en un f-string
  (`src/database/repository.py:358-379`). El panel usa su propio módulo
  `src/panel/queries.py` + `src/panel/db.py`, con SQL parametrizado explícito por
  endpoint. La imposibilidad de escribir es **estructural** (código separado, credencial
  separada, ni una sola sentencia `INSERT/UPDATE/DELETE` en el módulo), no una lista de
  operaciones prohibidas que alguien podría olvidar mantener.
- **API y copiloto comparten la misma capa de consultas** (`src/panel/queries.py`), para
  garantizar que un número en el panel y la misma pregunta al copiloto usen exactamente
  la misma consulta SQL y devuelvan el mismo resultado (criterio de aceptación §13.4).
- **El agente del panel no reutiliza el grafo de WhatsApp** (§2.1): es un grafo nuevo y
  más simple, sin supervisor multiagente, sin checkpointer, con herramientas limitadas
  exactamente a los endpoints de lectura de §7.

### 5.2 Secuencia de una consulta del copiloto (para orientar la implementación)

```text
Usuario escribe en el panel: "¿cuántos pacientes recuperables hay?"
        │
        ▼
CopilotKit (react-core) envía el mensaje al Copilot Runtime
        │
        ▼
Copilot Runtime (Next.js, /api/copilotkit) reenvía como HttpAgent (AG-UI)
        │  hacia AGENT_URL (servidor, nunca expuesto al navegador directamente)
        ▼
Endpoint AG-UI de FastAPI (ag_ui_langgraph.add_langgraph_fastapi_endpoint)
        │  agente "revylia_panel"
        ▼
Grafo LangGraph de solo lectura (Gemini) decide llamar la herramienta
"list_recoverable_patients" con clinic_id fijado en el servidor (nunca argumento del LLM)
        │
        ▼
src/panel/queries.py::list_recovery(conn, clinic_id, status=...)
        │  misma función que usa GET /api/v1/recovery
        ▼
Credencial de solo lectura → Supabase PostgreSQL
        │
        ▼
Resultado + fuente + filtros + generated_at → el modelo redacta la respuesta
        │
        ▼
AG-UI stream de vuelta → Copilot Runtime → UI del copiloto
(el panel muestra <QueryMeta> con source/filters/generated_at, igual que en la API REST)
```

---

## 6. Seguridad: identidad, `clinic_id`, credencial de solo lectura, RLS

### 6.1 `clinic_id` fijado en el servidor [NUEVO, invariante no negociable]

`clinic_id` se obtiene **siempre** de `REVYLIA_CLINIC_ID` en la configuración del
servidor FastAPI (misma variable ya usada por `Settings.revylia_clinic_id`, con default
actual `"clinica-sonrisas"`). Nunca se acepta como query param, header, body, ni como
argumento de ninguna herramienta del copiloto. Esto vale tanto para la API REST como para
el grafo LangGraph del panel: si el LLM del copiloto intenta pasar un `clinic_id`
distinto en una llamada de herramienta, el código de la herramienta debe ignorarlo y usar
siempre el valor de configuración del proceso.

### 6.2 Autenticación y autorización [NUEVO]

- El backend FastAPI verifica el JWT de Supabase **por sí mismo**; nunca confía en un
  header que diga quién es el usuario.
- Algoritmo asimétrico vía JWKS (`ES256`/`RS256`), descargado de `SUPABASE_JWKS_URL`
  (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`) y cacheado en memoria del proceso. No
  se usa secreto compartido HS256.
- Se valida: firma, `exp`, `iss == SUPABASE_JWT_ISSUER` (`{SUPABASE_URL}/auth/v1`),
  `aud == "authenticated"`.
- Habilitación de acceso: `app_metadata.revylia_panel === true`. **Nunca
  `user_metadata`** — esa sección del JWT es editable por el propio usuario autenticado, y
  cualquier cuenta invitada podría auto-habilitarse si el backend la leyera.
- El frontend envía `Authorization: Bearer <access_token>` en cada llamada a la API del
  panel.
- Sin token → `401 unauthorized`. Token válido pero sin `app_metadata.revylia_panel`
  → `403 forbidden`.
- En esta versión hay **un único perfil de personal autorizado**; no hay roles
  diferenciados ni administración multitenant. No hay selector de clínica en la UI.

### 6.3 Credencial PostgreSQL de solo lectura [NUEVO]

- Variable de entorno propia: `PANEL_DATABASE_URL`. **Nunca reutilizar `DATABASE_URL`**
  (esa es la del gateway de WhatsApp, con permisos de escritura, y no debe compartirse).
- El rol de base de datos detrás de `PANEL_DATABASE_URL` debe:
  - No ser propietario de ninguna tabla `revylia.*` (los dueños de tabla saltan RLS).
  - No tener el atributo `BYPASSRLS`.
  - Tener únicamente `GRANT SELECT` sobre las 7 tablas `revylia.*` — nada sobre
    `public.checkpoint*` (§3.2).
  - Idealmente, la conexión debe forzar `SET default_transaction_read_only = on` al
    abrir sesión (contrato §9: así lo hace `panel_connection()` en `src/panel/db.py`),
    como defensa adicional en profundidad, no como único mecanismo de protección.

### 6.4 RLS: el problema real y la migración pendiente [HONESTIDAD OBLIGATORIA]

`migrations/001_business.sql` (líneas 95-101) ejecuta:

```sql
ALTER TABLE revylia.clinics ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.escalations ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.recovery_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.whatsapp_inbound_events ENABLE ROW LEVEL SECURITY;
```

**En ningún lugar del archivo hay un solo `CREATE POLICY`.** El comentario en el propio
SQL (línea 93-94) lo dice sin rodeos: "Evita exposición accidental por Data API. El
backend conectado directamente a PostgreSQL con el rol de servidor sigue pudiendo
operar." Esto funciona hoy porque el gateway de WhatsApp se conecta con un rol que es
**dueño** de las tablas — en PostgreSQL, el dueño de una tabla omite RLS por defecto,
tenga o no políticas definidas.

**Consecuencia directa y verificada:** si hoy se creara el rol de solo lectura de §6.3 y
se le hiciera `GRANT SELECT` sobre estas tablas sin agregar ninguna política, ese rol
**recibiría cero filas en cada consulta, sin ningún mensaje de error** — porque RLS está
activo y, sin políticas `PERMISSIVE`, el comportamiento por defecto de PostgreSQL es
denegar todas las filas a cualquier rol no propietario. El panel completo aparentaría
funcionar (200 OK) y mostraría todo vacío, lo cual es peor que un error explícito porque
es indistinguible de "la clínica no tiene datos".

**Qué hay que hacer, y quién:**

1. Crear `migrations/003_panel_readonly.sql` (no existe todavía — solo existen `001` y
   `002` en `migrations/`) con:
   - El `CREATE ROLE` (o `GRANT` a un rol ya provisto por Supabase) para la credencial de
     solo lectura.
   - Una política `FOR SELECT` por tabla, con `USING (clinic_id = current_setting(...))`
     o el mecanismo equivalente que la implementación de `panel_connection()` decida usar
     para comunicar el `clinic_id` a PostgreSQL (p. ej. `SET LOCAL` de una variable de
     sesión personalizada leída por la política). El diseño exacto de la política queda a
     cargo de quien implemente `src/panel/db.py` y la migración; este documento no lo fija
     porque depende de decisiones de esa implementación (p. ej. si `PANEL_DATABASE_URL`
     sirve una sola clínica fija, la política puede ser tan simple como
     `USING (clinic_id = 'clinica-sonrisas')` codificado en la migración misma, dado que
     "sin selector de clínica" es una decisión de producto ya tomada).
   - Debe ejecutarla **una persona humana con credenciales administrativas** (igual que
     `scripts/setup_database.py` ejecuta hoy `001` y `002`), nunca un agente ni un paso
     automático de CI/CD sin supervisión.
2. **Antes de implementar nada del panel**, es requisito previo verificar que las
   migraciones de este repositorio (`001`, `002`) coinciden efectivamente con lo que hay
   desplegado en el proyecto Supabase real. Esta sesión no tuvo acceso a una base de
   datos desplegada ni a un proyecto Supabase real (ver §14): esa comparación no se pudo
   hacer aquí y queda como el primer paso operativo de la secuencia de implementación
   (§12, paso 1).

### 6.5 Zona horaria y separación de fechas de cita vs. timestamps de evento

- Valor inicial: `America/Bogota` (igual que hoy en `repository.py` y en
  `clinics.timezone`), sujeto a que se decida más adelante leer la columna
  `clinics.timezone` en vez de mantener el valor hardcodeado (§3.1).
- Las **fechas de cita** (`appointments.appointment_date`, `appointment_time`) son
  fechas/horas civiles, **sin zona horaria** — se muestran tal cual están almacenadas.
- Los **timestamps de evento** (`created_at`, `received_at`, `processed_at`, etc.,
  `TIMESTAMPTZ`) sí se convierten a `America/Bogota` para presentación, pero se
  serializan en la API como ISO-8601 UTC (ver §7.3) y es el frontend quien aplica la
  conversión de zona horaria para mostrarlos.

### 6.6 Textos almacenados como datos, nunca como instrucciones

Las columnas de texto libre identificadas en el diccionario de datos (§3.1) son:
`patients.notes`, `opportunities.reason`, `escalations.reason`,
`recovery_messages.message`, `whatsapp_inbound_events.response_text`. Todas pueden
contener contenido escrito por un flujo conversacional con un paciente real, incluyendo
intentos de inyección de instrucciones. El agente del panel debe recibir estos valores
siempre como datos citados dentro del contexto (p. ej. `"reason": "<texto>"` como valor
de una estructura, nunca concatenados en un system prompt como si fueran instrucciones
del operador), y nunca debe interpretarlos como comandos.

### 6.7 Prohibiciones explícitas del copiloto y de la API

- Prohibido SQL libre generado por el LLM.
- Prohibidas herramientas de escritura de cualquier tipo.
- Prohibidas herramientas de diagnóstico (inspección de esquema, `EXPLAIN`, listar
  tablas, etc.).
- Prohibido que `clinic_id` sea un argumento controlable por el modelo o por el cliente.
- Prohibido un checkpointer en `src/panel_agent/`: la conversación del copiloto vive solo
  en la sesión del navegador; no hay persistencia entre dispositivos en esta versión, y no
  se reutilizan los checkpoints de WhatsApp bajo ningún concepto.
- Secretos (DSN, JWKS, API keys) solo en variables de entorno del servidor, nunca en el
  cliente. Las trazas (Langfuse, si se activa) no deben contener contenido sensible;
  Langfuse es opcional para el panel igual que lo es hoy para el gateway
  (`REVYLIA_DISABLE_LANGFUSE`).

---

## 7. Contratos de consulta — API del panel (`GET /api/v1/...`) [NUEVO]

Esta sección resume, con el nivel de detalle necesario para implementar sin ambigüedad,
el contrato ya congelado en `docs/CONTRACT_PANEL.md` §3-§5 y §9. Ante cualquier
discrepancia entre esta sección y `docs/CONTRACT_PANEL.md`, ese archivo es la fuente de
verdad para este repositorio (así lo declara su propio encabezado); este documento debe
seguir siendo consistente con él porque describe el mismo sistema para un proyecto
independiente.

### 7.1 Reglas transversales

- Todas las rutas son `GET`. No existe ningún verbo de escritura.
- Paginación por offset por defecto: `limit=25` (máximo `100`), `offset=0`.
- **Orden estable:** todo `ORDER BY` termina en `, id DESC`, para que la paginación no
  produzca filas repetidas o saltadas cuando hay empates en la columna principal de orden.
- **Serialización de `BIGINT`:** todo `id` y `patient_id` se serializa como `string` en
  JSON (JavaScript pierde precisión numérica sobre 2^53; los `BIGSERIAL` de este esquema
  pueden superarlo con el tiempo). En TypeScript el tipo de estos campos es siempre
  `string`, nunca `number`.
- `DATE` → `"YYYY-MM-DD"`. `TIME` → `"HH:MM"`. `TIMESTAMPTZ` → ISO-8601 UTC.

### 7.2 Envoltura de respuesta

Toda respuesta de lista:

```json
{
  "data": [ /* ... */ ],
  "meta": {
    "source": "revylia.patients",
    "filters": { "status": "active" },
    "generated_at": "2026-09-12T15:04:05Z",
    "limit": 25,
    "offset": 0,
    "total": 137,
    "next_cursor": null
  }
}
```

Respuesta de detalle: `{ "data": {...}, "meta": { "source": ..., "generated_at": ... } }`.

Error (siempre esta forma; nunca traza, stack ni SQL crudo):

```json
{ "error": { "type": "validation_error", "message": "..." } }
```

`type` ∈ `unauthorized | forbidden | not_found | validation_error | upstream_unavailable`.

**Distinguir "sin datos" de "fallo":** una consulta sin resultados es `200` con
`"data": []` (o `"data": {}`/`null` según el endpoint de detalle) — nunca un error. Un
fallo real de conexión a la base de datos es `503 upstream_unavailable`. El frontend debe
renderizar estos dos casos de forma visualmente distinta (`<EmptyState>` vs.
`<ErrorState>`, contrato §7 de componentes de UI, ver §9 de este documento).

### 7.3 Tabla de endpoints

| Endpoint | Query params | Orden |
|---|---|---|
| `GET /api/v1/summary` | — | — |
| `GET /api/v1/patients` | `query`, `status` (`active`\|`inactive`), `consent` (bool), `limit`, `offset` | `name ASC, id DESC` |
| `GET /api/v1/patients/{id}` | — | — |
| `GET /api/v1/appointments` | `date_from`, `date_to`, `status`, `limit`, `offset` | `appointment_date DESC, appointment_time DESC, id DESC` |
| `GET /api/v1/availability` | `date` (**requerido**, `YYYY-MM-DD`) | — |
| `GET /api/v1/opportunities` | `status`, `min_score`, `limit`, `offset` | `score DESC, created_at DESC, id DESC` |
| `GET /api/v1/escalations` | `status`, `priority`, `limit`, `offset` | `priority_rank ASC, created_at DESC, id DESC` |
| `GET /api/v1/recovery` | `status`, `limit`, `offset` | `created_at DESC, id DESC` |
| `GET /api/v1/events` | `status`, `cursor`, `limit` | `received_at DESC, id DESC` |
| `GET /api/v1/catalog` | — | — |

### 7.4 `/patients`

`query` filtra `name ILIKE %q%` **O** `phone LIKE %q%`, con la consulta parametrizada y
escapando `%` y `_` del valor del usuario antes de interpolar el patrón `LIKE`. Campos
devueltos: `id, name, phone, last_visit_date, last_service, status, consent_marketing,
notes, created_at`. `GET /patients/{id}` añade `appointments` (últimas 20) y
`opportunities` (últimas 20) del paciente. Id inexistente → `404 not_found`.

Dado que `name` no es único (§3.1), dos búsquedas por el mismo nombre pueden devolver
varios registros: la UI y el copiloto deben mostrar siempre `id` (o al menos `phone`)
junto al nombre para desambiguar homónimos, nunca asumir que un nombre identifica a un
único paciente.

### 7.5 `/appointments`

`JOIN patients` para obtener `patient_name`. Como `appointments.patient_id` es
`NOT NULL`, **siempre hay paciente** en este listado (a diferencia de `opportunities` y
`escalations`). Campos: `id, patient_id, patient_name, service, appointment_date,
appointment_time, status, created_at, updated_at`.

### 7.6 `/availability` — replicar exactamente la semántica de hoy

Debe copiar literalmente el comportamiento de
`ClinicRepository.list_available_slots` (`src/database/repository.py:92-119`), **no
reinventarlo desde `CLINIC_KNOWLEDGE`**:

- Domingo (`weekday()==6`) → `[]`.
- Sábado (`weekday()==5`) → slots `08:00, 09:00, 10:00, 11:00`. Resto de días → slots
  `08:00` a `16:00` en punto.
- `duration_minutes` se ignora, siempre.
- Ocupado = existe cita ese día/hora con `status IN ('confirmed','pending')`.

Esas horas están hardcodeadas en Python y solo coinciden por casualidad con los horarios
publicados en `CLINIC_KNOWLEDGE`. Si se reimplementa esta lógica en vez de reutilizarla
literalmente, el panel y el agente de WhatsApp divergirán silenciosamente en cuanto
alguien cambie uno de los dos lugares.

Respuesta: `{"data": {"date","weekday","is_open","slots":[{"time","available"}]},
"meta":{}}`.

### 7.7 `/escalations`

`priority_rank`: `urgent=0, high=1, medium=2, low=3`, calculado con un `CASE` en SQL, no
en Python (para que el `ORDER BY priority_rank ASC` sea empujable al motor de base de
datos).

### 7.8 `/events` — paginación por keyset, no por offset

`whatsapp_inbound_events` tiene como PK `message_id TEXT`; `received_at` **no** es una
columna de ordenación estable por sí sola (pueden existir empates de timestamp).
Cursor = `(received_at, id)` codificado en base64;
`WHERE (received_at, id) < (:cursor_ts, :cursor_id)`. Campos devueltos: `message_id,
status, error_type, received_at, processed_at, response_text`.

**`from_number_hash` no se expone nunca.** Y no existe ruta de `JOIN` de un evento a un
paciente (§3.3, §4.2): este módulo muestra únicamente estado de procesamiento del
webhook, nunca un hilo de conversación. La UI de este módulo debe decirlo explícitamente
en un texto visible, no solo en la documentación técnica.

Nota de rendimiento (no bloqueante): el único índice existente sobre esta tabla es
`idx_revylia_events_clinic_received (clinic_id, received_at DESC)`, que no cubre por
completo el par `(received_at, id)` que usa el cursor. Es candidato razonable a agregar en
`migrations/003_panel_readonly.sql` un índice compuesto `(clinic_id, received_at DESC, id
DESC)`, pero no es un requisito para que la funcionalidad sea correcta, solo para que
escale mejor.

### 7.9 `/catalog`

Devuelve `CLINIC_KNOWLEDGE` completo (servicios, precios, duración, horarios, reglas)
como configuración versionada de solo lectura — no existe tabla de catálogo real (§4.3).
`meta.source = "config:CLINIC_KNOWLEDGE"`, `meta.pending_validation = true`. Esta bandera
debe mostrarse en la UI para dejar claro que ese catálogo puede no reflejar la
configuración comercial real de la clínica (§4.6).

### 7.10 `/summary` — fórmulas deterministas

Cada KPI documenta qué estados incluye y qué campo temporal usa. `hoy` = fecha actual en
`America/Bogota`.

| Clave | Fórmula |
|---|---|
| `patients_total` | `COUNT(patients)` |
| `patients_active` | `status='active'` |
| `patients_inactive` | `status='inactive'` |
| `patients_recoverable` | `consent_marketing AND status='inactive' AND last_visit_date <= hoy-180d` |
| `appointments_today` | `appointment_date = hoy AND status IN ('confirmed','pending')` |
| `appointments_next_7d` | `appointment_date BETWEEN hoy AND hoy+7 AND status IN ('confirmed','pending')` |
| `appointments_cancelled_30d` | `status='cancelled' AND appointment_date >= hoy-30d` |
| `opportunities_open` | `status='open'` |
| `escalations_pending` | `status='pending'` |
| `escalations_urgent_pending` | `status='pending' AND priority='urgent'` |
| `recovery_drafts` | `status='draft'` |
| `events_24h_total` | `received_at >= now()-24h` |
| `events_24h_failed` | `received_at >= now()-24h AND status='failed'` |

Forma de respuesta: `{"data":{"<clave>":{"value":0,"formula":"texto"}}, "meta":{}}`.
Recordatorio de §4.7: los filtros por `status` de `opportunities`, `escalations` y
`recovery_messages` dependen de convenciones de aplicación, no de un `CHECK` de base de
datos — si en algún momento se inserta un valor de `status` no contemplado en estas
fórmulas, el KPI correspondiente simplemente no contará esa fila, sin error visible.

### 7.11 Capa de consultas compartida — firmas exactas (`src/panel/queries.py`)

Toda función recibe una conexión ya abierta y `clinic_id` explícito (obtenido siempre de
la configuración del servidor, nunca del cliente). Toda función devuelve
`dict`/`list[dict]` ya serializados según §7.1 (ids como `str`):

```python
def get_summary(conn, clinic_id: str) -> dict: ...

def list_patients(conn, clinic_id: str, *, query: str | None = None,
                  status: str | None = None, consent: bool | None = None,
                  limit: int = 25, offset: int = 0) -> tuple[list[dict], int]: ...

def get_patient(conn, clinic_id: str, patient_id: int) -> dict | None: ...

def list_appointments(conn, clinic_id: str, *, date_from: date | None = None,
                      date_to: date | None = None, status: str | None = None,
                      limit: int = 25, offset: int = 0) -> tuple[list[dict], int]: ...

def get_availability(conn, clinic_id: str, day: date) -> dict: ...

def list_opportunities(conn, clinic_id: str, *, status: str | None = None,
                       min_score: int | None = None,
                       limit: int = 25, offset: int = 0) -> tuple[list[dict], int]: ...

def list_escalations(conn, clinic_id: str, *, status: str | None = None,
                     priority: str | None = None,
                     limit: int = 25, offset: int = 0) -> tuple[list[dict], int]: ...

def list_recovery(conn, clinic_id: str, *, status: str | None = None,
                  limit: int = 25, offset: int = 0) -> tuple[list[dict], int]: ...

def list_events(conn, clinic_id: str, *, status: str | None = None,
                cursor: str | None = None,
                limit: int = 25) -> tuple[list[dict], str | None]: ...

def get_catalog() -> dict: ...   # no toca BD; lee CLINIC_KNOWLEDGE
```

`tuple[list, int]` = `(filas, total)` para paginación por offset.
`tuple[list, str | None]` = `(filas, next_cursor)` para keyset (§7.8).

Y `src/panel/db.py` expone:

```python
@contextmanager
def panel_connection(settings=None): ...   # DSN de solo lectura, autocommit,
                                           # prepare_threshold=None, dict_row,
                                           # y SET default_transaction_read_only = on
```

---

## 8. Contrato del copiloto (`src/panel_agent/`) [NUEVO]

- Grafo LangGraph de **solo lectura**, Gemini vía `REVYLIA_MODEL` (mismo modelo/variable
  que hoy usa el gateway; el copiloto puede usar un valor distinto si se decide, pero por
  defecto hereda la misma configuración).
- Expuesto con `ag_ui_langgraph.add_langgraph_fastapi_endpoint` +
  `copilotkit.LangGraphAGUIAgent`. Nombre del agente: `revylia_panel`.
- En Next.js: `@copilotkit/runtime/v2` → `CopilotRuntime` + `createCopilotRuntimeHandler`
  (`mode: "single-route"`), agente representado como `HttpAgent` de `@ag-ui/client`.
  **Generación v2 en ambos lados — no mezclar con `remoteEndpoints` v1.** (Ver nota de
  §1.3 sobre verificar esta API contra la versión de paquete realmente instalada.)
- Herramientas = exactamente las funciones de `src/panel/queries.py` (§7.11), las mismas
  que usa la API REST — mismo resultado garantizado por construcción, no por
  coincidencia.
- Prohibido (repetido de §6.7 en su forma operativa): SQL libre, escritura, herramientas
  de diagnóstico, `clinic_id` como argumento del modelo, checkpointer.
- Toda respuesta del copiloto adjunta **fuente, filtros y `generated_at`**, igual que la
  API REST (mismo `meta` de §7.2), para que el usuario pueda distinguir una respuesta
  fundamentada en datos de una alucinación del modelo.
- Los textos de base de datos (§6.6) se pasan al modelo como datos citados, nunca como
  instrucción.
- Referencias oficiales a seguir para la integración exacta: [Copilot Runtime](https://docs.copilotkit.ai/langgraph-python/copilot-runtime)
  y [AG-UI para LangGraph](https://github.com/ag-ui-protocol/ag-ui/blob/main/integrations/langgraph/python/README.md).

---

## 9. Contrato de componentes de UI [NUEVO]

`web/components/shell/`:

- `<AppShell>{children}</AppShell>` — sidebar + header, responsive.
- `<PageHeader title description? actions? />`.

`web/components/data/`:

- `<KpiCard label value hint? tone? icon? />` — `tone`: `default|warning|danger|success`.
- `<DataTable columns data emptyMessage isLoading? />` — genérico sobre TanStack Table
  (`@tanstack/react-table`, ya instalado).
- `<StatusBadge status kind />` — `kind`:
  `appointment|patient|opportunity|escalation|recovery|event`.
- `<QueryMeta meta />` — renderiza `source`, `filters`, `generated_at` (§7.2/§8).
- `<EmptyState title description? />` — para "sin datos" (no es un error).
- `<ErrorState title description? onRetry? />` — para "fallo de consulta" (§7.2).

`web/lib/api/client.ts` — `panelFetch<T>(path, params?)`: adjunta el Bearer, normaliza la
envoltura de §7.2 y lanza `PanelApiError {type, message}` ante un error.

`web/lib/types.ts` — espejo exacto de los campos de §7. `id` y `patient_id` siempre
`string`.

Todo el texto visible en **español**. Fechas formateadas con `date-fns` (ya instalado,
`^4.4.0`) y locale `es`.

---

## 10. Configuración por componente (valores ficticios)

Ninguno de los valores siguientes es una credencial real; son ejemplos de forma para
completar en cada entorno.

### 10.1 Backend FastAPI (proceso existente + router nuevo del panel)

```env
# Ya existentes (gateway de WhatsApp)
REVYLIA_ENV=production
REVYLIA_CLINIC_ID=clinica-sonrisas
REVYLIA_MODEL=gemini-3.1-flash-lite
GOOGLE_API_KEY=AIza-EJEMPLO-NO-REAL
DATABASE_URL=postgresql://revylia_app:EJEMPLO@aws-0-us-east-1.pooler.supabase.com:6543/postgres
DATABASE_URL_ADMIN=postgresql://postgres:EJEMPLO@db.xxxxxxxx.supabase.co:5432/postgres
REVYLIA_DISABLE_LANGFUSE=true

# Nuevas para el panel
PANEL_DATABASE_URL=postgresql://revylia_panel_ro:EJEMPLO@aws-0-us-east-1.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://xxxxxxxx.supabase.co
SUPABASE_JWT_ISSUER=https://xxxxxxxx.supabase.co/auth/v1
SUPABASE_JWKS_URL=https://xxxxxxxx.supabase.co/auth/v1/.well-known/jwks.json
```

### 10.2 Frontend Next.js (`web/`)

```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxxxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ-EJEMPLO-NO-REAL
PANEL_API_URL=http://localhost:8000
AGENT_URL=http://localhost:8000/api/panel-agent
```

`PANEL_API_URL` y `AGENT_URL` se leen solo en el servidor de Next.js (rutas API/Server
Actions), nunca en el cliente, para no exponer la topología interna del backend.

### 10.3 Rol de solo lectura en PostgreSQL (ejemplo de forma, ejecutar como admin)

```sql
-- Ilustrativo. La forma final depende de cómo panel_connection() comunique
-- el clinic_id a las políticas (ver §6.4). Ejecutar en migrations/003_panel_readonly.sql.
CREATE ROLE revylia_panel_ro LOGIN PASSWORD 'EJEMPLO-NO-REAL' NOSUPERUSER NOBYPASSRLS;
GRANT USAGE ON SCHEMA revylia TO revylia_panel_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA revylia TO revylia_panel_ro;
-- + una política FOR SELECT por tabla (pendiente de diseño final, ver §6.4).
```

---

## 11. Despliegue — estado real y deuda técnica conocida

### 11.1 Lo que hay hoy [VERIFICADO]

`src/main.py` instancia un único objeto `FastAPI()` y le registra el router de WhatsApp
más los dos endpoints de salud. `pyproject.toml` declara:

```toml
[tool.vercel]
entrypoint = "src.main:app"
```

Es decir: **un único entry point de despliegue**. El contrato congelado
(`docs/CONTRACT_PANEL.md` §0.4) autoriza como única modificación a código existente dos
líneas aditivas en `src/main.py` (un `import` y un `include_router` del router del
panel) — nada más. Esa es precisamente la instrucción que, al ejecutarse, **coloca el
router del panel en el mismo proceso, el mismo `app` de FastAPI y el mismo despliegue de
Vercel que el webhook de WhatsApp.**

### 11.2 Por qué esto es deuda técnica, no un logro

El plan original (`PLAN_APPWEB_REVYLIA.md`, sección "Añadir configuración por componente
... despliegue separado del gateway") pedía que el panel se desplegara de forma separada
del webhook. **Eso no se logró en esta implementación.** Compartir proceso y despliegue
tiene consecuencias reales: un pico de tráfico del copiloto puede afectar la latencia del
webhook de WhatsApp (y viceversa); un despliegue del panel obliga a redeployar también el
gateway; y las variables de entorno de ambos sistemas conviven en el mismo runtime,
aumentando la superficie si alguna se filtra por error de configuración.

Esto se documenta aquí sin atenuantes: **no se presenta como cumplido**. Es una limitación
conocida del estado actual del repositorio en la rama `feat/panel-web`, aceptada como
punto de partida operativo por el contrato §0.4 (que restringe a dos líneas los cambios
permitidos sobre `src/main.py`), no como el diseño final deseado.

### 11.3 Ruta para separarlo después

Cuando se decida invertir en la separación real:

1. Extraer `src/panel/` (routers, `queries.py`, `db.py`) a su propio paquete ASGI, con su
   propio `FastAPI()` y su propio archivo de entrada (p. ej. `src/panel_app.py`).
2. Declarar un segundo proyecto de despliegue en Vercel (o la plataforma que se use) con
   su propio `entrypoint` apuntando a ese archivo, y sus propias variables de entorno
   (`PANEL_DATABASE_URL`, `SUPABASE_*`), sin heredar las del gateway de WhatsApp.
3. El mismo criterio aplica al agente del copiloto (`src/panel_agent/`, endpoint AG-UI):
   puede vivir en el mismo proceso separado del panel o en uno propio, pero en cualquier
   caso fuera del proceso del webhook.
4. Actualizar `PANEL_API_URL` y `AGENT_URL` en la configuración de Next.js para apuntar
   al nuevo dominio/servicio separado.
5. Retirar el `import` + `include_router` añadidos en `src/main.py`, devolviendo ese
   archivo a contener únicamente el webhook y la salud del gateway.

Este es trabajo pendiente explícito, no cubierto por el alcance actual de ningún agente
en la sesión que originó este documento.

---

## 12. Secuencia de implementación

El orden es obligatorio porque cada etapa depende de que la anterior esté verificada, no
solo construida:

1. **Acceso y permisos.**
   - Verificar (persona con acceso administrativo a Supabase) que las migraciones
     `001`/`002` de este repositorio coinciden con el esquema realmente desplegado.
   - Crear y ejecutar `migrations/003_panel_readonly.sql`: rol de solo lectura + políticas
     `FOR SELECT` por tabla (§6.3, §6.4).
   - Confirmar, con una consulta manual usando la nueva credencial, que devuelve filas
     reales (no cero silencioso) para la clínica configurada.
   - Configurar `app_metadata.revylia_panel = true` en la cuenta de Supabase Auth del
     único perfil de personal autorizado en esta versión.
2. **API** (`src/panel/**`).
   - `db.py` (conexión de solo lectura) y `queries.py` (firmas exactas de §7.11).
   - Routers `GET /api/v1/...` de §7, verificación de JWT vía JWKS, envoltura de
     respuesta y errores de §7.2.
   - Dos líneas aditivas en `src/main.py` (import + `include_router`), único cambio
     permitido a código existente.
3. **Panel** (`web/app/(panel)/**`, componentes de §9).
   - Autenticación (`web/app/(auth)/**`, `web/middleware.ts`, Supabase Auth).
   - Módulos: resumen, agenda, pacientes, oportunidades, escalaciones, recuperación,
     eventos — cada uno consumiendo `panelFetch` contra los endpoints de §7.
4. **Copiloto** (`src/panel_agent/**`, `web/app/api/copilotkit/route.ts`,
   `web/components/copilot/**`).
   - Grafo de solo lectura sobre las mismas funciones de `queries.py`.
   - Integración Copilot Runtime v2 + AG-UI (verificar primero la nota de §1.3/§8 sobre la
     versión de paquete instalada).
5. **Validación** — ejecutar íntegramente las pruebas de aceptación de §13 antes de dar
   por cerrada la implementación.

---

## 13. Pruebas de aceptación

Agrupadas exactamente según los puntos exigidos en la sección "Validación y entrega" del
plan original. Cada una debe poder ejecutarse contra un entorno real (no solo revisarse
por lectura de código) antes de considerar el panel listo.

### 13.1 Acceso

- **Acceso autorizado:** un usuario con `app_metadata.revylia_panel === true` y token
  vigente puede iniciar sesión y ver todos los módulos.
- **Sesión vencida:** un token expirado (`exp` pasado) recibe `401 unauthorized` en cada
  endpoint y el frontend redirige a login sin mostrar datos parciales.
- **Usuario sin habilitación:** una cuenta válida en Supabase Auth pero sin
  `app_metadata.revylia_panel === true` recibe `403 forbidden` en la API y el frontend
  muestra un estado de acceso denegado, no un panel vacío.

### 13.2 Imposibilidad de escribir

- Un intento de `POST/PUT/PATCH/DELETE` contra cualquier ruta `/api/v1/...` debe fallar
  (no existen esos verbos registrados; `405` o `404` según el router).
- Una petición al copiloto que pida explícitamente "crea una cita", "cancela la cita X" o
  equivalente debe resultar en que el agente explique que no puede escribir, sin invocar
  ninguna herramienta de escritura (porque no existen en su grafo).
- Una consulta manual con la credencial `PANEL_DATABASE_URL` que intente
  `INSERT/UPDATE/DELETE` sobre cualquier tabla `revylia.*` debe fallar por permisos
  (el rol no tiene esos `GRANT`), no por lógica de aplicación.

### 13.3 Rechazo de cambio de clínica

- Enviar `clinic_id` en el body, header o query string de cualquier endpoint no debe
  tener ningún efecto: la respuesta debe reflejar siempre `REVYLIA_CLINIC_ID` del
  servidor. Verificar explícitamente enviando un `clinic_id` distinto al configurado y
  confirmando que la respuesta no cambia.
- Pedirle al copiloto explícitamente que consulte "la clínica X" (una distinta a la
  configurada) debe resultar en una respuesta que aclare que el sistema opera sobre una
  única clínica, sin que ninguna herramienta reciba ese valor como argumento.

### 13.4 Coincidencia panel / copiloto / referencia

- Para al menos tres KPIs de `/summary` (p. ej. `patients_active`,
  `appointments_today`, `escalations_urgent_pending`), comparar: (a) el valor mostrado en
  el panel, (b) la respuesta del copiloto a la pregunta equivalente en lenguaje natural, y
  (c) una consulta SQL de referencia ejecutada manualmente con la fórmula exacta de §7.10.
  Los tres deben coincidir exactamente.

### 13.5 Casos de datos

- **Fechas:** una cita con `appointment_date` de hoy aparece en `appointments_today`; una
  de mañana no. Verificar el límite exacto del rango en `appointments_next_7d`.
- **Estados:** filtrar `/patients?status=inactive` y `/appointments?status=cancelled`
  devuelve únicamente filas con ese valor exacto.
- **Registros sin paciente asociado:** crear (fuera del panel, con la vía existente del
  gateway o directamente en BD de prueba) una `opportunity` y una `escalation` con
  `patient_id IS NULL`; verificar que `/opportunities` y `/escalations` las listan sin
  error, usando `patient_name`/`reason` como único dato disponible. (No aplica a
  `/appointments` ni `/recovery`: sus `patient_id` son `NOT NULL` por esquema, §3.1.)
- **Homónimos:** con dos pacientes de igual `name` (posible por ausencia de unicidad en
  esa columna, §3.1), verificar que `/patients?query=<nombre>` devuelve ambos con `id`
  distinto, y que la UI y el copiloto los distinguen por `id`/`phone`, nunca solo por
  nombre.
- **Paginación:** solicitar una segunda página (`offset=25` o el `cursor` de `/events`)
  y verificar que no repite ni omite filas respecto de la primera página, dado el orden
  estable de §7.1.

### 13.6 Resiliencia

- **Fallo de Supabase:** con `PANEL_DATABASE_URL` apuntando a un host inválido o
  inalcanzable, cada endpoint debe responder `503 upstream_unavailable` con la forma de
  error de §7.2 (nunca una traza cruda), y el panel debe mostrar `<ErrorState>` con opción
  de reintentar.
- **Fallo de Gemini:** con la clave de API inválida o el servicio de Gemini inalcanzable,
  el copiloto debe fallar de forma contenida (mensaje de error visible en la UI del
  copiloto) sin afectar a los módulos REST del panel, que deben seguir funcionando con
  normalidad.
- **Fallo de streaming:** si la conexión AG-UI se corta a mitad de una respuesta del
  copiloto, la UI debe indicarlo (no quedar cargando indefinidamente) y permitir reintentar
  la pregunta.
- En los tres casos anteriores, confirmar que el panel (módulos REST) sigue funcionando
  de forma independiente del estado del copiloto, y viceversa cuando aplique.

### 13.7 Ausencia de secretos y datos sensibles en salidas técnicas

- Ninguna respuesta de error de la API (§7.2) debe contener el DSN, el JWT recibido, ni
  ningún fragmento de SQL.
- Ninguna traza (si Langfuse está activo) debe contener `PANEL_DATABASE_URL`,
  `GOOGLE_API_KEY`, tokens de acceso, ni el contenido de las columnas de texto libre de
  §6.6 sin el mismo enmascarado que ya aplica el gateway de WhatsApp.
- Ninguna respuesta de la API o del copiloto debe exponer `from_number_hash` (prohibido
  explícitamente en §7.8) ni ningún dato de las tablas de checkpoints de `public` (§3.2).

---

## 14. Qué quedó sin verificar en esta sesión

Listado explícito, sin ambigüedad, de lo que este documento **no** pudo comprobar porque
no hubo una base de datos desplegada ni un proyecto Supabase real disponible durante su
elaboración:

- Si el esquema realmente desplegado en el proyecto Supabase de la clínica coincide con
  `migrations/001_business.sql` y `migrations/002_seed_demo.sql` de este repositorio. Las
  dos copias sueltas en la raíz del repo (`001_business.sql`, `002_seed_demo.sql`,
  archivos sin seguimiento de git según `git status`) se compararon byte a byte contra
  las de `migrations/` en esta sesión: el contenido es **idéntico**, solo difiere el
  terminador de línea (LF vs. CRLF). Esto descarta una divergencia de contenido entre esas
  dos copias locales, pero **no dice nada** sobre si `migrations/` coincide con lo
  desplegado en Supabase — esa comparación es la que sigue pendiente y es requisito previo
  a implementar (§6.4, §12 paso 1).
- El esquema de columnas interno de las tablas de checkpoint de LangGraph
  (`public.checkpoints`, `checkpoint_blobs`, `checkpoint_writes`,
  `checkpoint_migrations`): no está en este repositorio, lo define la librería en tiempo
  de ejecución (§3.2).
- Si `@copilotkit/runtime@^1.71.1` (versión realmente instalada en `web/package.json`)
  expone el patrón `/v2` con `CopilotRuntime` + `createCopilotRuntimeHandler` en la forma
  exacta que describe `docs/CONTRACT_PANEL.md` §6 (§1.3, §8).
- El comportamiento real de streaming AG-UI entre el endpoint FastAPI y el Copilot
  Runtime bajo fallo parcial de red (§13.6): se describe el comportamiento esperado, no se
  ejecutó una prueba real.
- Cualquier configuración de RLS, roles o políticas que exista hoy en el proyecto
  Supabase real más allá de lo que declara `migrations/001_business.sql` (por ejemplo, si
  alguien ya creó manualmente políticas fuera de las migraciones versionadas).
- El contenido de `.env.example`: git status muestra ese archivo como eliminado
  (`D .env.example`) en el árbol de trabajo actual; no se reconstruyó su contenido para
  este documento, y los nombres de variables aquí citados provienen de
  `src/core/config.py` y de `docs/CONTRACT_PANEL.md`, no de ese archivo.

Ningún archivo de código, esquema ni dato fue modificado para producir este documento.
