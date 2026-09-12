# Especificación de Revylia Web con CopilotKit

## Entregable

Crear `docs/REVYLIA_WEB_COPILOTKIT_SPEC.md`, en español, como documento autónomo que pueda entregarse a otro desarrollador o agente para construir la app en un proyecto independiente.

El documento distinguirá **componentes existentes**, **componentes nuevos** y **limitaciones verificadas en el repositorio**. Incluirá diagramas de arquitectura, diccionario de datos, contratos de consulta, configuración, etapas de implementación y criterios de aceptación.

## Decisiones de producto

- Panel interno para el personal de una sola clínica.
- Toda la aplicación será de solo lectura, incluido el copiloto.
- Acceso mediante Supabase Auth: cuentas individuales por invitación, correo y contraseña, sin registro público.
- Un único perfil de personal autorizado en esta versión.
- Interfaz en español, adaptable a escritorio y móvil.
- Sin selector de clínica, administración multitenant, edición de registros ni envío de mensajes.
- Módulos: resumen operativo, agenda, pacientes, oportunidades, escalaciones, recuperación y monitor de eventos de WhatsApp.
- Copiloto lateral para consultar datos, resumir resultados, aplicar filtros y abrir registros del panel.

## Contenido técnico del Markdown

### Contexto de Revylia y datos disponibles

Documentar el stack actual: Python 3.12, FastAPI, Pydantic, LangGraph, LangChain, Gemini, psycopg, Supabase PostgreSQL, PostgresSaver, WhatsApp Cloud API, Langfuse y despliegue configurado para Vercel. Registrar las versiones declaradas y el papel de cada componente.

Describir el flujo actual de WhatsApp, supervisor y especialistas de recepción, agenda, recuperación y Clinic Brain. Explicar que `invoke_revylia()` puede provocar escrituras y no será el agente del panel.

Incluir el diccionario completo de las siete tablas `revylia.*`: campos, tipos, nulabilidad, relaciones, estados, valores predeterminados e índices. Separar las tablas de checkpoints de los datos operativos.

Documentar estas limitaciones:

- Actualmente existen endpoints de salud y webhook, pero no una API del panel.
- Los eventos de WhatsApp contienen estado de procesamiento y respuesta, pero no un historial completo de mensajes ni una relación directa con pacientes.
- Servicios, precios, duración y reglas están en `CLINIC_KNOWLEDGE`; no existen tablas para ese catálogo.
- La agenda utiliza franjas horarias y un único cupo por clínica, fecha y hora; no modela profesionales, consultorios ni ocupación por duración.
- No existen datos suficientes para facturación, ingresos reales o métricas de conversión atribuida.
- Los datos demo no representan necesariamente la configuración real de la clínica.

### Arquitectura de la nueva app

Especificar este flujo:

```text
Personal → Next.js + CopilotKit
                 ├─ Supabase Auth
                 ├─ API del panel → FastAPI de consulta
                 └─ Copilot Runtime → AG-UI → LangGraph de consulta
                                                ↓
                                  Repositorio de solo lectura
                                                ↓
                                   Supabase de Revylia
```

- Frontend con Next.js App Router, TypeScript y Tailwind CSS.
- Backend FastAPI independiente, con consultas parametrizadas compartidas entre API y herramientas del agente.
- Agente LangGraph específico de lectura, usando Gemini y herramientas permitidas explícitamente.
- Copilot Runtime en Next.js y adaptador oficial AG-UI para FastAPI/LangGraph. Documentar una pareja compatible de proveedor y transporte, evitando mezclar ejemplos de distintas generaciones. Referencias: [Copilot Runtime](https://docs.copilotkit.ai/langgraph-python/copilot-runtime) y [AG-UI para LangGraph](https://github.com/ag-ui-protocol/ag-ui/blob/main/integrations/langgraph/python/README.md).
- Conversación web limitada a la sesión, sin persistencia entre dispositivos en esta versión. No reutilizar checkpoints de WhatsApp.
- Catálogo informativo trasladado como configuración versionada, identificando su origen y pendiente de validación antes de producción.

### Seguridad, contratos y comportamiento

- Mantener `clinic_id` por compatibilidad, fijado en configuración del servidor y fuera de los parámetros controlables por el cliente.
- Validar identidad y autorización en el runtime y backend; permitir únicamente usuarios invitados con habilitación administrada en metadatos protegidos.
- Usar una credencial PostgreSQL exclusiva de lectura, sin propiedad de tablas ni `BYPASSRLS`, con permisos y políticas `SELECT` para la clínica configurada. No reutilizar credenciales administrativas. [Referencia de RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).
- Definir endpoints `GET /api/v1/...` para resumen, pacientes, citas, disponibilidad, oportunidades, escalaciones, recuperación, eventos y configuración informativa.
- Especificar filtros, paginación, orden estable, respuestas de detalle, errores y serialización segura de identificadores `BIGINT`.
- Calcular indicadores mediante consultas deterministas, documentando fórmula, estados incluidos y campo temporal utilizado.
- Usar `America/Bogota` como valor inicial, sujeto a la configuración real de la clínica. Separar fechas de citas de timestamps de eventos.
- Mostrar fuente, filtros y momento de consulta en resultados del copiloto; distinguir ausencia de datos de fallos de consulta.
- Prohibir SQL libre, herramientas de escritura y diagnósticos. Tratar textos almacenados como datos, sin ejecutar instrucciones contenidas en ellos.
- Mantener secretos en servidor y trazas sin contenido sensible; Langfuse será opcional.

## Validación y entrega

El Markdown incluirá pruebas de aceptación para:

- Acceso autorizado, sesión vencida y usuario sin habilitación.
- Imposibilidad de escribir tanto por API como mediante el agente o la credencial SQL.
- Rechazo de intentos de cambiar la clínica.
- Coincidencia entre cifras del panel, respuestas del copiloto y consultas de referencia.
- Fechas, estados, registros sin paciente asociado, homónimos y resultados paginados.
- Fallos de Supabase, Gemini y streaming, conservando el funcionamiento independiente del panel.
- Ausencia de secretos, checkpoints o datos sensibles en respuestas técnicas y trazas.

Añadir configuración por componente, ejemplos con valores ficticios, despliegue separado del gateway y una secuencia de implementación: acceso y permisos → API → panel → copiloto → validación.

La elaboración del archivo no modificará código, esquema ni datos. El contexto de base de datos se identificará como verificado contra las migraciones del repositorio; la comprobación de diferencias con la base desplegada quedará como requisito previo a implementar.
