"""Herramientas de SOLO LECTURA del copiloto del panel.

Una herramienta por endpoint de §5 del contrato. Toda consulta delega en
`src/panel/queries.py` (§9): aquí no se escribe SQL, no se escribe en la base
de datos y no se expone diagnóstico técnico (§6).

`clinic_id` NUNCA es argumento de herramienta (§0.2): se lee de la
configuración del servidor (`REVYLIA_CLINIC_ID`) dentro de cada herramienta.

Cada resultado lleva `meta` con `source`, `filters` y `generated_at` (§4).
"""

from datetime import date, datetime, timezone
from typing import Any

from langchain_core.tools import tool

from src.panel.config import get_panel_settings
from src.panel.db import panel_connection
from src.panel.queries import (
    get_availability,
    get_catalog,
    get_patient,
    get_summary,
    list_appointments,
    list_escalations,
    list_events,
    list_opportunities,
    list_patients,
    list_recovery,
)

LIMITE_POR_DEFECTO = 25
LIMITE_MAXIMO = 100

MENSAJE_FALLO_BD = "No fue posible consultar la base de datos del panel en este momento."


class _DatoInvalido(ValueError):
    """Argumento inválido enviado por el modelo. Su texto sí es mostrable."""


def _ahora_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resultado(data: Any, source: str, filters: dict[str, Any], **meta: Any) -> dict:
    """Envoltura de §4. `data` vacío significa SIN DATOS, nunca fallo."""
    return {
        "data": data,
        "meta": {
            "source": source,
            "filters": {clave: valor for clave, valor in filters.items() if valor is not None},
            "generated_at": _ahora_utc(),
            **meta,
        },
    }


def _error(tipo: str, mensaje: str) -> dict:
    """Envoltura de error de §4: sin traza, sin SQL, sin detalle interno."""
    return {"error": {"type": tipo, "message": mensaje}}


def _pagina(limit: Any, offset: Any = 0) -> tuple[int, int]:
    try:
        limite = int(limit)
        desplazamiento = int(offset)
    except (TypeError, ValueError):
        raise _DatoInvalido("`limit` y `offset` deben ser números enteros.") from None
    if limite < 1:
        raise _DatoInvalido("`limit` debe ser mayor o igual a 1.")
    if desplazamiento < 0:
        raise _DatoInvalido("`offset` no puede ser negativo.")
    return min(limite, LIMITE_MAXIMO), desplazamiento


def _fecha(valor: str, campo: str) -> date:
    try:
        return date.fromisoformat(str(valor))
    except (TypeError, ValueError):
        raise _DatoInvalido(f"`{campo}` debe tener el formato YYYY-MM-DD.") from None


def _fecha_opcional(valor: str | None, campo: str) -> date | None:
    return None if valor is None else _fecha(valor, campo)


def _identificador(valor: str, campo: str) -> int:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        raise _DatoInvalido(f"`{campo}` debe ser un identificador numérico.") from None


@tool("panel_resumen")
def panel_resumen() -> dict:
    """Indicadores (KPIs) del panel: pacientes, citas, oportunidades,
    escalamientos, recuperación y eventos de WhatsApp. Cada indicador incluye
    su fórmula. Úsala para preguntas globales del tipo "¿cómo vamos?"."""
    try:
        settings = get_panel_settings()
        with panel_connection(settings) as conn:
            datos = get_summary(conn, settings.revylia_clinic_id)
    except Exception:
        return _error("upstream_unavailable", MENSAJE_FALLO_BD)
    return _resultado(datos, "revylia.summary", {})


@tool("panel_listar_pacientes")
def panel_listar_pacientes(
    query: str | None = None,
    status: str | None = None,
    consent: bool | None = None,
    limit: int = LIMITE_POR_DEFECTO,
    offset: int = 0,
) -> dict:
    """Lista pacientes de la clínica.

    `query` busca por nombre o teléfono. `status` es "active" o "inactive".
    `consent` filtra por consentimiento de marketing. `limit` máximo 100.
    Devuelve `meta.total` con el total de coincidencias."""
    filtros = {"query": query, "status": status, "consent": consent}
    try:
        limite, desplazamiento = _pagina(limit, offset)
        settings = get_panel_settings()
        with panel_connection(settings) as conn:
            filas, total = list_patients(
                conn,
                settings.revylia_clinic_id,
                query=query,
                status=status,
                consent=consent,
                limit=limite,
                offset=desplazamiento,
            )
    except _DatoInvalido as exc:
        return _error("validation_error", str(exc))
    except Exception:
        return _error("upstream_unavailable", MENSAJE_FALLO_BD)
    return _resultado(
        filas,
        "revylia.patients",
        filtros,
        limit=limite,
        offset=desplazamiento,
        total=total,
    )


@tool("panel_obtener_paciente")
def panel_obtener_paciente(patient_id: str) -> dict:
    """Ficha de un paciente por su identificador, con sus últimas 20 citas y
    sus últimas 20 oportunidades. El identificador es una cadena numérica."""
    try:
        identificador = _identificador(patient_id, "patient_id")
        settings = get_panel_settings()
        with panel_connection(settings) as conn:
            paciente = get_patient(conn, settings.revylia_clinic_id, identificador)
    except _DatoInvalido as exc:
        return _error("validation_error", str(exc))
    except Exception:
        return _error("upstream_unavailable", MENSAJE_FALLO_BD)
    if paciente is None:
        return _error("not_found", f"No existe un paciente con id {patient_id}.")
    return _resultado(paciente, "revylia.patients", {"patient_id": str(patient_id)})


@tool("panel_listar_citas")
def panel_listar_citas(
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    limit: int = LIMITE_POR_DEFECTO,
    offset: int = 0,
) -> dict:
    """Lista citas con el nombre del paciente.

    `date_from` y `date_to` en formato YYYY-MM-DD (fechas civiles de la
    clínica). `status` típico: confirmed, pending, cancelled, completed."""
    filtros = {"date_from": date_from, "date_to": date_to, "status": status}
    try:
        limite, desplazamiento = _pagina(limit, offset)
        desde = _fecha_opcional(date_from, "date_from")
        hasta = _fecha_opcional(date_to, "date_to")
        settings = get_panel_settings()
        with panel_connection(settings) as conn:
            filas, total = list_appointments(
                conn,
                settings.revylia_clinic_id,
                date_from=desde,
                date_to=hasta,
                status=status,
                limit=limite,
                offset=desplazamiento,
            )
    except _DatoInvalido as exc:
        return _error("validation_error", str(exc))
    except Exception:
        return _error("upstream_unavailable", MENSAJE_FALLO_BD)
    return _resultado(
        filas,
        "revylia.appointments",
        filtros,
        limit=limite,
        offset=desplazamiento,
        total=total,
    )


@tool("panel_consultar_disponibilidad")
def panel_consultar_disponibilidad(day: str) -> dict:
    """Disponibilidad de agenda de un día concreto (YYYY-MM-DD, obligatorio).

    Devuelve los bloques de una hora en punto y si están libres u ocupados.
    Domingo siempre cerrado; sábado solo hasta el mediodía."""
    try:
        fecha = _fecha(day, "day")
        settings = get_panel_settings()
        with panel_connection(settings) as conn:
            datos = get_availability(conn, settings.revylia_clinic_id, fecha)
    except _DatoInvalido as exc:
        return _error("validation_error", str(exc))
    except Exception:
        return _error("upstream_unavailable", MENSAJE_FALLO_BD)
    return _resultado(datos, "revylia.availability", {"day": day})


@tool("panel_listar_oportunidades")
def panel_listar_oportunidades(
    status: str | None = None,
    min_score: int | None = None,
    limit: int = LIMITE_POR_DEFECTO,
    offset: int = 0,
) -> dict:
    """Lista oportunidades comerciales detectadas por el agente de WhatsApp.

    `status` típico: open, won, lost. `min_score` filtra por puntaje mínimo.
    Ordenadas por puntaje descendente."""
    filtros = {"status": status, "min_score": min_score}
    try:
        limite, desplazamiento = _pagina(limit, offset)
        settings = get_panel_settings()
        with panel_connection(settings) as conn:
            filas, total = list_opportunities(
                conn,
                settings.revylia_clinic_id,
                status=status,
                min_score=min_score,
                limit=limite,
                offset=desplazamiento,
            )
    except _DatoInvalido as exc:
        return _error("validation_error", str(exc))
    except Exception:
        return _error("upstream_unavailable", MENSAJE_FALLO_BD)
    return _resultado(
        filas,
        "revylia.opportunities",
        filtros,
        limit=limite,
        offset=desplazamiento,
        total=total,
    )


@tool("panel_listar_escalamientos")
def panel_listar_escalamientos(
    status: str | None = None,
    priority: str | None = None,
    limit: int = LIMITE_POR_DEFECTO,
    offset: int = 0,
) -> dict:
    """Lista escalamientos a un humano.

    `status` típico: pending, resolved. `priority`: urgent, high, medium, low.
    Ordenados por prioridad (urgent primero) y luego por fecha."""
    filtros = {"status": status, "priority": priority}
    try:
        limite, desplazamiento = _pagina(limit, offset)
        settings = get_panel_settings()
        with panel_connection(settings) as conn:
            filas, total = list_escalations(
                conn,
                settings.revylia_clinic_id,
                status=status,
                priority=priority,
                limit=limite,
                offset=desplazamiento,
            )
    except _DatoInvalido as exc:
        return _error("validation_error", str(exc))
    except Exception:
        return _error("upstream_unavailable", MENSAJE_FALLO_BD)
    return _resultado(
        filas,
        "revylia.escalations",
        filtros,
        limit=limite,
        offset=desplazamiento,
        total=total,
    )


@tool("panel_listar_recuperacion")
def panel_listar_recuperacion(
    status: str | None = None,
    limit: int = LIMITE_POR_DEFECTO,
    offset: int = 0,
) -> dict:
    """Lista los mensajes de recuperación de pacientes inactivos.

    `status` típico: draft, approved, sent. Consultar un borrador NO lo
    aprueba ni lo envía: eso requiere una persona fuera del copiloto."""
    filtros = {"status": status}
    try:
        limite, desplazamiento = _pagina(limit, offset)
        settings = get_panel_settings()
        with panel_connection(settings) as conn:
            filas, total = list_recovery(
                conn,
                settings.revylia_clinic_id,
                status=status,
                limit=limite,
                offset=desplazamiento,
            )
    except _DatoInvalido as exc:
        return _error("validation_error", str(exc))
    except Exception:
        return _error("upstream_unavailable", MENSAJE_FALLO_BD)
    return _resultado(
        filas,
        "revylia.recovery_messages",
        filtros,
        limit=limite,
        offset=desplazamiento,
        total=total,
    )


@tool("panel_listar_eventos")
def panel_listar_eventos(
    status: str | None = None,
    cursor: str | None = None,
    limit: int = LIMITE_POR_DEFECTO,
) -> dict:
    """Estado de procesamiento de los mensajes entrantes de WhatsApp.

    NO es un hilo de conversación y no puede asociarse a un paciente: solo se
    guarda el estado del procesamiento. `status` típico: processed, failed.
    Para la página siguiente, reenvía el `meta.next_cursor` recibido."""
    filtros = {"status": status, "cursor": cursor}
    try:
        limite, _ = _pagina(limit)
        settings = get_panel_settings()
        with panel_connection(settings) as conn:
            filas, siguiente = list_events(
                conn,
                settings.revylia_clinic_id,
                status=status,
                cursor=cursor,
                limit=limite,
            )
    except _DatoInvalido as exc:
        return _error("validation_error", str(exc))
    except Exception:
        return _error("upstream_unavailable", MENSAJE_FALLO_BD)
    return _resultado(
        filas,
        "revylia.whatsapp_inbound_events",
        filtros,
        limit=limite,
        next_cursor=siguiente,
    )


@tool("panel_consultar_catalogo")
def panel_consultar_catalogo() -> dict:
    """Catálogo de la clínica: servicios, precios, duraciones, horarios y
    reglas. Es configuración versionada, no una tabla, y está PENDIENTE DE
    VALIDACIÓN: adviértelo siempre que cites un precio."""
    try:
        datos = get_catalog()
    except Exception:
        return _error("upstream_unavailable", "No fue posible leer el catálogo.")
    return _resultado(datos, "config:CLINIC_KNOWLEDGE", {}, pending_validation=True)


PANEL_TOOLS = [
    panel_resumen,
    panel_listar_pacientes,
    panel_obtener_paciente,
    panel_listar_citas,
    panel_consultar_disponibilidad,
    panel_listar_oportunidades,
    panel_listar_escalamientos,
    panel_listar_recuperacion,
    panel_listar_eventos,
    panel_consultar_catalogo,
]
