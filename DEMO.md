# Demo del panel Revylia — guion rápido

## Arrancar (2 comandos)

```bash
cd web
pnpm build && pnpm start     # http://localhost:3000
```

Usa **`pnpm start`** (producción), no `pnpm dev`: el indicador flotante de
desarrollo de Next.js tapa el pie del menú lateral y además arranca más lento.

Si algo falla y hay prisa: `pnpm dev` también funciona.

## Estado: modo demostración

El panel arranca **sin backend, sin base de datos y sin login**. Los datos salen
de `web/lib/demo/fixtures.ts`, derivados de `migrations/002_seed_demo.sql`.

Esto es deliberado, no un atajo escondido: el pie de cada página muestra
`demo:fixtures` y la hora de consulta, así que en pantalla queda claro de dónde
vienen los números.

Se activa el modo real definiendo variables de entorno (ninguna está definida hoy):

| Variable | Efecto al definirla |
|---|---|
| `PANEL_API_URL` | `panelFetch` deja de usar fixtures y llama a la API FastAPI |
| `AGENT_URL` | Monta el copiloto real; sin ella sale el panel "no conectado" |
| `PANEL_AUTH_ENABLED=true` | El middleware exige sesión de Supabase |

**Antes de presentar**: comprueba que NO existe `web/.env.local`. Si alguien
define ahí `AGENT_URL`, el copiloto intenta conectarse y muestra errores de
conexión en vez del panel de demostración.

## Recorrido sugerido (5 minutos)

1. **Resumen** (`/`) — 13 indicadores. Cada tarjeta muestra **la fórmula exacta**
   con la que se calcula. Las cifras se derivan de las mismas filas que ves en
   los otros módulos, así que cuadran entre sí.
2. **Agenda** (`/agenda`) — citas + disponibilidad del día. Señala el aviso:
   franjas de 1 hora y un único cupo por clínica/fecha/hora.
3. **Pacientes** (`/pacientes`) — busca `Carlos`: salen **dos homónimos**,
   distinguibles por teléfono y última visita.
4. **Oportunidades** (`/oportunidades`) — hay filas **sin paciente asociado**
   (`patient_id` es nullable); se muestran con nombre/teléfono sueltos.
5. **Escalaciones** (`/escalaciones`) — ordenadas por prioridad; una urgente.
6. **Recuperación** (`/recuperacion`) — borradores. El panel **no envía nada**.
7. **Eventos** (`/eventos`) — aviso importante: es **estado de procesamiento**,
   no un historial de conversación, y **no hay relación con pacientes**.
8. **Copiloto** — botón flotante abajo a la derecha. Hoy es una maqueta honesta:
   dice que el agente no está conectado y no inventa respuestas.

También: el conmutador de tema (claro/oscuro) arriba a la derecha, y el menú
lateral colapsa con **Ctrl+B**.

## Qué decir si preguntan

- **"¿Son datos reales?"** No. Son datos de demostración derivados del seed del
  repositorio. La app está construida contra el esquema real (`revylia.*`) y el
  contrato de la API ya está escrito e implementado.
- **"¿Por qué el copiloto no responde?"** El agente de consulta existe
  (`src/panel_agent/`) pero necesita base de datos y clave de Gemini. No hay
  ninguna de las dos en este entorno.
- **"¿Cuánto falta para producción?"** Ver "Pendiente" abajo. El trabajo grueso
  de API, agente y permisos ya está escrito; falta conectarlo a infraestructura
  real y verificarlo contra ella.

## Pendiente (construido pero NO demostrable hoy)

| Pieza | Estado | Qué falta |
|---|---|---|
| API de solo lectura (`src/panel/`) | Escrita, 54 tests en verde sin BD | Ejecutarla contra PostgreSQL real |
| `migrations/003_panel_readonly.sql` | Escrita | **La ejecuta una persona con credenciales admin.** Crea rol de solo lectura + 7 políticas RLS |
| Copiloto (`src/panel_agent/`) | Escrito, 91 tests en verde | Instalar extras `[panel]`, BD y `GOOGLE_API_KEY` |
| Auth Supabase | Escrita, desactivada | Proyecto Supabase + invitar usuarios con `app_metadata.revylia_panel = true` |

### Dos cosas que hay que resolver antes de producción

1. **RLS sin políticas.** `migrations/001_business.sql` activa RLS en las 7
   tablas y no define ninguna política. El gateway de WhatsApp funciona sólo
   porque conecta como rol **dueño** de las tablas. Un rol de solo lectura con
   `GRANT SELECT` recibiría **cero filas en todas las consultas, sin error** —
   el panel se vería vacío y parecería un problema de datos. Por eso `003` crea
   las políticas `FOR SELECT`. **Hay que verificar el esquema desplegado en
   Supabase contra las migraciones del repositorio antes de implementar.**

2. **El copiloto necesita un checkpointer.** `ag_ui_langgraph` llama a
   `graph.aget_state()`, que sobre un grafo compilado sin checkpointer lanza
   `ValueError: No checkpointer set` **en la primera petición**, no al importar.
   El contrato lo prohibía para evitar persistencia entre dispositivos; la
   solución es `MemorySaver()` (en memoria, por sesión), que respeta la
   intención: no usa Postgres ni reutiliza los checkpoints de WhatsApp. Está
   comentado en el sitio exacto de `src/panel_agent/graph.py`.

## Documentos

- `docs/REVYLIA_WEB_COPILOTKIT_SPEC.md` — especificación técnica completa (1276 líneas)
- `docs/CONTRACT_PANEL.md` — contrato de API, componentes y consultas
