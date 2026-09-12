"""Rutas de solo lectura del panel (§5 del contrato).

`clinic_id` SIEMPRE sale de la configuración del servidor
(`settings.revylia_clinic_id`). No se declara como query param, header ni
body en ninguna ruta: es estructuralmente inalcanzable desde la petición.

La envoltura de §4 y el formato de error se aplican con `route_class`
(`PanelRoute`), no con `exception_handler`, porque los handlers se
registran en la instancia `FastAPI` y `src/main.py` está fuera del alcance
de escritura de este agente. `PanelRoute` envuelve también la resolución
de dependencias, así que los 401/403 de `require_panel_user` salen con la
forma correcta.
"""

from __future__ import annotations

import logging
from datetime import date as Date, datetime, timezone
from typing import Annotated, Any, Callable, Coroutine

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from src.panel import queries
from src.panel.auth import PanelUserDep
from src.panel.config import PanelSettings, get_panel_settings
from src.panel.db import panel_connection
from src.panel.errors import PanelError, not_found, validation_error
from src.panel.schemas import (
    AppointmentOut,
    AvailabilityOut,
    DetailMeta,
    DetailResponse,
    ErrorResponse,
    EscalationOut,
    EventOut,
    ListMeta,
    ListResponse,
    OpportunityOut,
    PatientDetailOut,
    PatientOut,
    RecoveryOut,
    SummaryMetric,
)


logger = logging.getLogger("revylia.panel")

PATIENT_STATUSES = {"active", "inactive"}
APPOINTMENT_STATUSES = {"pending", "confirmed", "cancelled", "completed"}
ESCALATION_PRIORITIES = {"low", "medium", "high", "urgent"}
EVENT_STATUSES = {"processing", "completed", "failed"}


# =====================================================================
# Envoltura de errores (§4)
# =====================================================================


def _error_response(status_code: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"type": error_type, "message": message}},
    )


class PanelRoute(APIRoute):
    """Traduce cualquier fallo a `{"error": {"type", "message"}}`.

    Nunca se filtra una traza, un mensaje de psycopg ni una consulta SQL.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_handler = super().get_route_handler()

        async def panel_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except PanelError as exc:
                return _error_response(exc.status_code, exc.error_type, exc.message)
            except RequestValidationError:
                return _error_response(
                    400,
                    "validation_error",
                    "Parámetros de consulta inválidos.",
                )
            except Exception:
                # Sin datos != fallo: aquí solo llegan fallos reales
                # (base de datos caída, error de serialización...).
                logger.exception("Fallo al resolver una ruta del panel")
                return _error_response(
                    503,
                    "upstream_unavailable",
                    "No se pudo consultar la información en este momento. "
                    "Intenta de nuevo en unos segundos.",
                )

        return panel_handler


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Parámetros inválidos"},
    401: {"model": ErrorResponse, "description": "Sin token válido"},
    403: {"model": ErrorResponse, "description": "Cuenta sin habilitación"},
    404: {"model": ErrorResponse, "description": "Recurso inexistente"},
    503: {"model": ErrorResponse, "description": "Base de datos no disponible"},
}

router = APIRouter(
    prefix="/api/v1",
    tags=["Panel"],
    route_class=PanelRoute,
    responses=ERROR_RESPONSES,
)


# =====================================================================
# Dependencias
# =====================================================================

SettingsDep = Annotated[PanelSettings, Depends(get_panel_settings)]


def get_conn(settings: SettingsDep):
    """Conexión de solo lectura por petición. Es una dependencia (y no una
    llamada directa) para que los tests la sustituyan con un doble."""
    with panel_connection(settings) as conn:
        yield conn


ConnDep = Annotated[Any, Depends(get_conn)]


# =====================================================================
# Helpers de meta (§4)
# =====================================================================


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _filters(**kwargs: Any) -> dict[str, Any]:
    """Solo los filtros efectivamente aplicados. `clinic_id` nunca aparece:
    no es un filtro del cliente, es una condición fija del servidor."""
    return {
        key: (value.isoformat() if isinstance(value, Date) else value)
        for key, value in kwargs.items()
        if value is not None
    }


def _list_meta(
    source: str,
    filters: dict[str, Any],
    *,
    limit: int | None = None,
    offset: int | None = None,
    total: int | None = None,
    next_cursor: str | None = None,
) -> ListMeta:
    return ListMeta(
        source=source,
        filters=filters,
        generated_at=_now_iso(),
        limit=limit,
        offset=offset,
        total=total,
        next_cursor=next_cursor,
    )


def _detail_meta(
    source: str,
    *,
    filters: dict[str, Any] | None = None,
    pending_validation: bool | None = None,
) -> DetailMeta:
    return DetailMeta(
        source=source,
        generated_at=_now_iso(),
        filters=filters,
        pending_validation=pending_validation,
    )


def _require_choice(value: str | None, allowed: set[str], name: str) -> str | None:
    if value is None:
        return None
    if value not in allowed:
        raise validation_error(
            f"Valor no válido para '{name}'. Opciones: {', '.join(sorted(allowed))}."
        )
    return value


# =====================================================================
# Endpoints
# =====================================================================


@router.get("/summary", response_model=DetailResponse[dict[str, SummaryMetric]])
def read_summary(user: PanelUserDep, conn: ConnDep, settings: SettingsDep):
    data = queries.get_summary(conn, settings.revylia_clinic_id)
    return {"data": data, "meta": _detail_meta("revylia.summary")}


@router.get("/patients", response_model=ListResponse[PatientOut])
def read_patients(
    user: PanelUserDep,
    conn: ConnDep,
    settings: SettingsDep,
    query: str | None = None,
    status: str | None = None,
    consent: bool | None = None,
    limit: int = queries.DEFAULT_LIMIT,
    offset: int = 0,
):
    status = _require_choice(status, PATIENT_STATUSES, "status")
    limit, offset = queries.clamp_limit(limit), queries.clamp_offset(offset)

    rows, total = queries.list_patients(
        conn,
        settings.revylia_clinic_id,
        query=query,
        status=status,
        consent=consent,
        limit=limit,
        offset=offset,
    )
    return {
        "data": rows,
        "meta": _list_meta(
            "revylia.patients",
            _filters(query=query, status=status, consent=consent),
            limit=limit,
            offset=offset,
            total=total,
        ),
    }


@router.get("/patients/{patient_id}", response_model=DetailResponse[PatientDetailOut])
def read_patient(
    patient_id: str,
    user: PanelUserDep,
    conn: ConnDep,
    settings: SettingsDep,
):
    # `patient_id` llega como string (§3) y se valida a mano para devolver
    # la forma de error del contrato en vez del 422 de FastAPI.
    try:
        numeric_id = int(patient_id)
    except (TypeError, ValueError) as exc:
        raise validation_error("El identificador del paciente debe ser numérico.") from exc

    patient = queries.get_patient(conn, settings.revylia_clinic_id, numeric_id)
    if patient is None:
        raise not_found("No existe un paciente con ese identificador en la clínica.")
    return {"data": patient, "meta": _detail_meta("revylia.patients")}


@router.get("/appointments", response_model=ListResponse[AppointmentOut])
def read_appointments(
    user: PanelUserDep,
    conn: ConnDep,
    settings: SettingsDep,
    date_from: Date | None = None,
    date_to: Date | None = None,
    status: str | None = None,
    limit: int = queries.DEFAULT_LIMIT,
    offset: int = 0,
):
    status = _require_choice(status, APPOINTMENT_STATUSES, "status")
    if date_from and date_to and date_from > date_to:
        raise validation_error("'date_from' no puede ser posterior a 'date_to'.")
    limit, offset = queries.clamp_limit(limit), queries.clamp_offset(offset)

    rows, total = queries.list_appointments(
        conn,
        settings.revylia_clinic_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "data": rows,
        "meta": _list_meta(
            "revylia.appointments",
            _filters(date_from=date_from, date_to=date_to, status=status),
            limit=limit,
            offset=offset,
            total=total,
        ),
    }


@router.get("/availability", response_model=DetailResponse[AvailabilityOut])
def read_availability(
    user: PanelUserDep,
    conn: ConnDep,
    settings: SettingsDep,
    date: Annotated[Date, Query(description="Día a consultar, YYYY-MM-DD")],
):
    data = queries.get_availability(conn, settings.revylia_clinic_id, date)
    return {
        "data": data,
        "meta": _detail_meta(
            "revylia.appointments", filters=_filters(date=date)
        ),
    }


@router.get("/opportunities", response_model=ListResponse[OpportunityOut])
def read_opportunities(
    user: PanelUserDep,
    conn: ConnDep,
    settings: SettingsDep,
    status: str | None = None,
    min_score: int | None = None,
    limit: int = queries.DEFAULT_LIMIT,
    offset: int = 0,
):
    if min_score is not None and not 0 <= min_score <= 100:
        raise validation_error("'min_score' debe estar entre 0 y 100.")
    limit, offset = queries.clamp_limit(limit), queries.clamp_offset(offset)

    rows, total = queries.list_opportunities(
        conn,
        settings.revylia_clinic_id,
        status=status,
        min_score=min_score,
        limit=limit,
        offset=offset,
    )
    return {
        "data": rows,
        "meta": _list_meta(
            "revylia.opportunities",
            _filters(status=status, min_score=min_score),
            limit=limit,
            offset=offset,
            total=total,
        ),
    }


@router.get("/escalations", response_model=ListResponse[EscalationOut])
def read_escalations(
    user: PanelUserDep,
    conn: ConnDep,
    settings: SettingsDep,
    status: str | None = None,
    priority: str | None = None,
    limit: int = queries.DEFAULT_LIMIT,
    offset: int = 0,
):
    priority = _require_choice(priority, ESCALATION_PRIORITIES, "priority")
    limit, offset = queries.clamp_limit(limit), queries.clamp_offset(offset)

    rows, total = queries.list_escalations(
        conn,
        settings.revylia_clinic_id,
        status=status,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    return {
        "data": rows,
        "meta": _list_meta(
            "revylia.escalations",
            _filters(status=status, priority=priority),
            limit=limit,
            offset=offset,
            total=total,
        ),
    }


@router.get("/recovery", response_model=ListResponse[RecoveryOut])
def read_recovery(
    user: PanelUserDep,
    conn: ConnDep,
    settings: SettingsDep,
    status: str | None = None,
    limit: int = queries.DEFAULT_LIMIT,
    offset: int = 0,
):
    limit, offset = queries.clamp_limit(limit), queries.clamp_offset(offset)

    rows, total = queries.list_recovery(
        conn,
        settings.revylia_clinic_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "data": rows,
        "meta": _list_meta(
            "revylia.recovery_messages",
            _filters(status=status),
            limit=limit,
            offset=offset,
            total=total,
        ),
    }


@router.get("/events", response_model=ListResponse[EventOut])
def read_events(
    user: PanelUserDep,
    conn: ConnDep,
    settings: SettingsDep,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = queries.DEFAULT_LIMIT,
):
    status = _require_choice(status, EVENT_STATUSES, "status")
    limit = queries.clamp_limit(limit)

    try:
        rows, next_cursor = queries.list_events(
            conn,
            settings.revylia_clinic_id,
            status=status,
            cursor=cursor,
            limit=limit,
        )
    except ValueError as exc:
        raise validation_error("El cursor de paginación no es válido.") from exc

    return {
        "data": rows,
        "meta": _list_meta(
            "revylia.whatsapp_inbound_events",
            _filters(status=status, cursor=cursor),
            limit=limit,
            next_cursor=next_cursor,
        ),
    }


@router.get("/catalog", response_model=DetailResponse[dict[str, Any]])
def read_catalog(user: PanelUserDep):
    # No toca la base: es configuración versionada, pendiente de validación
    # por la clínica (§5.6).
    return {
        "data": queries.get_catalog(),
        "meta": _detail_meta("config:CLINIC_KNOWLEDGE", pending_validation=True),
    }
