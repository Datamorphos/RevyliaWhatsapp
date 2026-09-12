"""Capa de consultas compartida del panel (§9 del contrato).

Reglas que no se negocian:

* SOLO SELECT. Ninguna sentencia de este módulo escribe.
* SQL siempre parametrizado. Los valores del cliente jamás se concatenan
  en el SQL: los filtros opcionales se resuelven con el patrón
  `(%(param)s::tipo IS NULL OR columna = %(param)s)`, de modo que cada
  consulta es una constante de módulo fija.
* `clinic_id` aparece en el WHERE de TODAS las consultas y lo provee el
  llamador desde la configuración del servidor, nunca desde la petición.
* Todo BIGINT sale serializado como `str` (§3).

A2 (copiloto) importa este módulo sin modificarlo.
"""

from __future__ import annotations

import base64
import copy
from datetime import date as Date
from datetime import datetime, time as Time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from src.domain.knowledge import CLINIC_KNOWLEDGE


BOGOTA_TZ = ZoneInfo("America/Bogota")

# Horario de la clínica: réplica LITERAL de
# `ClinicRepository.list_available_slots`. Está hardcodeado en Python allá y
# aquí debe estar hardcodeado igual. NO derivar de CLINIC_KNOWLEDGE: si se
# reimplementa, el panel y el agente de WhatsApp divergen.
_FIRST_HOUR = 8
_SATURDAY_END_HOUR = 12
_WEEKDAY_END_HOUR = 17

MAX_LIMIT = 100
DEFAULT_LIMIT = 25


# =====================================================================
# Serialización (§3)
# =====================================================================


def today_bogota() -> Date:
    return datetime.now(BOGOTA_TZ).date()


def _sid(value: Any) -> str | None:
    """BIGINT -> str. JavaScript pierde precisión por encima de 2^53."""
    return None if value is None else str(value)


def _sdate(value: Any) -> str | None:
    """DATE -> 'YYYY-MM-DD'. Fecha civil, sin zona horaria."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, Date):
        return value.isoformat()
    return str(value)[:10]


def _stime(value: Any) -> str | None:
    """TIME -> 'HH:MM' (no 'HH:MM:SS', que es lo que daría .isoformat())."""
    if value is None:
        return None
    if isinstance(value, (Time, datetime)):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _sts(value: Any) -> str | None:
    """TIMESTAMPTZ -> ISO-8601 en UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat() + "Z"
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _like_pattern(value: str) -> str:
    """Patrón `%valor%` con `%`, `_` y `\\` escapados (§5.1).

    El SQL correspondiente declara `ESCAPE '\\'`.
    """
    escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_LIMIT))


def clamp_offset(offset: int) -> int:
    return max(0, int(offset))


# =====================================================================
# /summary  (§5.7)
# =====================================================================

_SUMMARY_SQL = """
SELECT
    (SELECT COUNT(*) FROM revylia.patients
      WHERE clinic_id = %(clinic_id)s) AS patients_total,
    (SELECT COUNT(*) FROM revylia.patients
      WHERE clinic_id = %(clinic_id)s AND status = 'active') AS patients_active,
    (SELECT COUNT(*) FROM revylia.patients
      WHERE clinic_id = %(clinic_id)s AND status = 'inactive') AS patients_inactive,
    (SELECT COUNT(*) FROM revylia.patients
      WHERE clinic_id = %(clinic_id)s
        AND consent_marketing = true
        AND status = 'inactive'
        AND last_visit_date <= %(cutoff_180)s) AS patients_recoverable,
    (SELECT COUNT(*) FROM revylia.appointments
      WHERE clinic_id = %(clinic_id)s
        AND appointment_date = %(today)s
        AND status IN ('confirmed', 'pending')) AS appointments_today,
    (SELECT COUNT(*) FROM revylia.appointments
      WHERE clinic_id = %(clinic_id)s
        AND appointment_date BETWEEN %(today)s AND %(next_7d)s
        AND status IN ('confirmed', 'pending')) AS appointments_next_7d,
    (SELECT COUNT(*) FROM revylia.appointments
      WHERE clinic_id = %(clinic_id)s
        AND status = 'cancelled'
        AND appointment_date >= %(cutoff_30)s) AS appointments_cancelled_30d,
    (SELECT COUNT(*) FROM revylia.opportunities
      WHERE clinic_id = %(clinic_id)s AND status = 'open') AS opportunities_open,
    (SELECT COUNT(*) FROM revylia.escalations
      WHERE clinic_id = %(clinic_id)s AND status = 'pending') AS escalations_pending,
    (SELECT COUNT(*) FROM revylia.escalations
      WHERE clinic_id = %(clinic_id)s
        AND status = 'pending'
        AND priority = 'urgent') AS escalations_urgent_pending,
    (SELECT COUNT(*) FROM revylia.recovery_messages
      WHERE clinic_id = %(clinic_id)s AND status = 'draft') AS recovery_drafts,
    (SELECT COUNT(*) FROM revylia.whatsapp_inbound_events
      WHERE clinic_id = %(clinic_id)s
        AND received_at >= now() - interval '24 hours') AS events_24h_total,
    (SELECT COUNT(*) FROM revylia.whatsapp_inbound_events
      WHERE clinic_id = %(clinic_id)s
        AND received_at >= now() - interval '24 hours'
        AND status = 'failed') AS events_24h_failed
"""

SUMMARY_FORMULAS: dict[str, str] = {
    "patients_total": "Total de pacientes de la clínica.",
    "patients_active": "Pacientes con status = 'active'.",
    "patients_inactive": "Pacientes con status = 'inactive'.",
    "patients_recoverable": (
        "Pacientes con consentimiento de marketing, status = 'inactive' y "
        "última visita anterior o igual a hoy - 180 días."
    ),
    "appointments_today": (
        "Citas de hoy (America/Bogota) con status en ('confirmed', 'pending')."
    ),
    "appointments_next_7d": (
        "Citas entre hoy y hoy + 7 días con status en ('confirmed', 'pending')."
    ),
    "appointments_cancelled_30d": (
        "Citas con status = 'cancelled' y fecha de cita desde hoy - 30 días."
    ),
    "opportunities_open": "Oportunidades con status = 'open'.",
    "escalations_pending": "Escalamientos con status = 'pending'.",
    "escalations_urgent_pending": (
        "Escalamientos con status = 'pending' y priority = 'urgent'."
    ),
    "recovery_drafts": "Mensajes de recuperación con status = 'draft'.",
    "events_24h_total": "Eventos de WhatsApp recibidos en las últimas 24 horas.",
    "events_24h_failed": (
        "Eventos de WhatsApp de las últimas 24 horas con status = 'failed'."
    ),
}


def get_summary(conn, clinic_id: str) -> dict:
    today = today_bogota()
    row = conn.execute(
        _SUMMARY_SQL,
        {
            "clinic_id": clinic_id,
            "today": today,
            "next_7d": today + timedelta(days=7),
            "cutoff_30": today - timedelta(days=30),
            "cutoff_180": today - timedelta(days=180),
        },
    ).fetchone()
    row = dict(row or {})
    return {
        key: {"value": int(row.get(key) or 0), "formula": formula}
        for key, formula in SUMMARY_FORMULAS.items()
    }


# =====================================================================
# /patients  (§5.1)
# =====================================================================

_PATIENTS_WHERE = """
    WHERE clinic_id = %(clinic_id)s
      AND (%(query)s::text IS NULL
           OR name ILIKE %(query)s ESCAPE '\\'
           OR phone LIKE %(query)s ESCAPE '\\')
      AND (%(status)s::text IS NULL OR status = %(status)s)
      AND (%(consent)s::boolean IS NULL OR consent_marketing = %(consent)s)
"""

# Las dos consultas se componen de la MISMA constante de WHERE para que el
# total y la página no puedan divergir. Solo se concatenan constantes de
# módulo: ningún valor del cliente entra en el SQL.
_PATIENTS_COUNT_SQL = (
    "SELECT COUNT(*) AS total FROM revylia.patients" + _PATIENTS_WHERE
)
_PATIENTS_SQL = (
    """
    SELECT id, name, phone, last_visit_date, last_service, status,
           consent_marketing, notes, created_at
    FROM revylia.patients
    """
    + _PATIENTS_WHERE
    + """
    ORDER BY name ASC, id DESC
    LIMIT %(limit)s OFFSET %(offset)s
    """
)


def _patient_row(row) -> dict:
    return {
        "id": _sid(row["id"]),
        "name": row["name"],
        "phone": row["phone"],
        "last_visit_date": _sdate(row["last_visit_date"]),
        "last_service": row["last_service"],
        "status": row["status"],
        "consent_marketing": bool(row["consent_marketing"]),
        "notes": row["notes"],
        "created_at": _sts(row["created_at"]),
    }


def list_patients(
    conn,
    clinic_id: str,
    *,
    query: str | None = None,
    status: str | None = None,
    consent: bool | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[dict], int]:
    params = {
        "clinic_id": clinic_id,
        "query": _like_pattern(query) if query else None,
        "status": status,
        "consent": consent,
    }
    total = int(conn.execute(_PATIENTS_COUNT_SQL, params).fetchone()["total"])
    rows = conn.execute(
        _PATIENTS_SQL,
        {**params, "limit": clamp_limit(limit), "offset": clamp_offset(offset)},
    ).fetchall()
    return [_patient_row(row) for row in rows], total


_PATIENT_SQL = """
    SELECT id, name, phone, last_visit_date, last_service, status,
           consent_marketing, notes, created_at
    FROM revylia.patients
    WHERE clinic_id = %(clinic_id)s AND id = %(patient_id)s
    LIMIT 1
"""

_PATIENT_APPOINTMENTS_SQL = """
    SELECT a.id, a.patient_id, p.name AS patient_name, a.service,
           a.appointment_date, a.appointment_time, a.status,
           a.created_at, a.updated_at
    FROM revylia.appointments a
    JOIN revylia.patients p
      ON p.id = a.patient_id AND p.clinic_id = a.clinic_id
    WHERE a.clinic_id = %(clinic_id)s AND a.patient_id = %(patient_id)s
    ORDER BY a.appointment_date DESC, a.appointment_time DESC, a.id DESC
    LIMIT 20
"""

_PATIENT_OPPORTUNITIES_SQL = """
    SELECT id, patient_id, patient_name, phone, reason, score, status, created_at
    FROM revylia.opportunities
    WHERE clinic_id = %(clinic_id)s AND patient_id = %(patient_id)s
    ORDER BY created_at DESC, id DESC
    LIMIT 20
"""


def get_patient(conn, clinic_id: str, patient_id: int) -> dict | None:
    params = {"clinic_id": clinic_id, "patient_id": patient_id}
    row = conn.execute(_PATIENT_SQL, params).fetchone()
    if not row:
        return None
    patient = _patient_row(row)
    patient["appointments"] = [
        _appointment_row(r)
        for r in conn.execute(_PATIENT_APPOINTMENTS_SQL, params).fetchall()
    ]
    patient["opportunities"] = [
        _opportunity_row(r)
        for r in conn.execute(_PATIENT_OPPORTUNITIES_SQL, params).fetchall()
    ]
    return patient


# =====================================================================
# /appointments  (§5.2)
# =====================================================================

_APPOINTMENTS_FROM = """
    FROM revylia.appointments a
    JOIN revylia.patients p
      ON p.id = a.patient_id AND p.clinic_id = a.clinic_id
    WHERE a.clinic_id = %(clinic_id)s
      AND (%(date_from)s::date IS NULL OR a.appointment_date >= %(date_from)s)
      AND (%(date_to)s::date IS NULL OR a.appointment_date <= %(date_to)s)
      AND (%(status)s::text IS NULL OR a.status = %(status)s)
"""

_APPOINTMENTS_COUNT_SQL = "SELECT COUNT(*) AS total" + _APPOINTMENTS_FROM
_APPOINTMENTS_SQL = (
    """
    SELECT a.id, a.patient_id, p.name AS patient_name, a.service,
           a.appointment_date, a.appointment_time, a.status,
           a.created_at, a.updated_at
    """
    + _APPOINTMENTS_FROM
    + """
    ORDER BY a.appointment_date DESC, a.appointment_time DESC, a.id DESC
    LIMIT %(limit)s OFFSET %(offset)s
    """
)


def _appointment_row(row) -> dict:
    return {
        "id": _sid(row["id"]),
        "patient_id": _sid(row["patient_id"]),
        "patient_name": row["patient_name"],
        "service": row["service"],
        "appointment_date": _sdate(row["appointment_date"]),
        "appointment_time": _stime(row["appointment_time"]),
        "status": row["status"],
        "created_at": _sts(row["created_at"]),
        "updated_at": _sts(row["updated_at"]),
    }


def list_appointments(
    conn,
    clinic_id: str,
    *,
    date_from: Date | None = None,
    date_to: Date | None = None,
    status: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[dict], int]:
    params = {
        "clinic_id": clinic_id,
        "date_from": date_from,
        "date_to": date_to,
        "status": status,
    }
    total = int(conn.execute(_APPOINTMENTS_COUNT_SQL, params).fetchone()["total"])
    rows = conn.execute(
        _APPOINTMENTS_SQL,
        {**params, "limit": clamp_limit(limit), "offset": clamp_offset(offset)},
    ).fetchall()
    return [_appointment_row(row) for row in rows], total


# =====================================================================
# /availability  (§5.3) — réplica literal de list_available_slots
# =====================================================================

_BOOKED_SLOTS_SQL = """
    SELECT appointment_time
    FROM revylia.appointments
    WHERE clinic_id = %(clinic_id)s
      AND appointment_date = %(day)s
      AND status IN ('confirmed', 'pending')
"""


def get_availability(conn, clinic_id: str, day: Date) -> dict:
    """Disponibilidad del día. `duration_minutes` NO participa: los slots
    son de una hora en punto, igual que en `ClinicRepository`.
    """
    weekday = day.weekday()

    # Domingo: cerrado.
    if weekday == 6:
        return {
            "date": day.isoformat(),
            "weekday": weekday,
            "is_open": False,
            "slots": [],
        }

    end_hour = _SATURDAY_END_HOUR if weekday == 5 else _WEEKDAY_END_HOUR
    candidate_slots = [f"{hour:02d}:00" for hour in range(_FIRST_HOUR, end_hour)]

    rows = conn.execute(
        _BOOKED_SLOTS_SQL, {"clinic_id": clinic_id, "day": day}
    ).fetchall()

    booked = {
        row["appointment_time"].strftime("%H:%M")
        if hasattr(row["appointment_time"], "strftime")
        else str(row["appointment_time"])[:5]
        for row in rows
    }

    return {
        "date": day.isoformat(),
        "weekday": weekday,
        "is_open": True,
        "slots": [
            {"time": slot, "available": slot not in booked} for slot in candidate_slots
        ],
    }


# =====================================================================
# /opportunities
# =====================================================================

_OPPORTUNITIES_WHERE = """
    WHERE clinic_id = %(clinic_id)s
      AND (%(status)s::text IS NULL OR status = %(status)s)
      AND (%(min_score)s::integer IS NULL OR score >= %(min_score)s)
"""

_OPPORTUNITIES_COUNT_SQL = (
    "SELECT COUNT(*) AS total FROM revylia.opportunities" + _OPPORTUNITIES_WHERE
)
_OPPORTUNITIES_SQL = (
    """
    SELECT id, patient_id, patient_name, phone, reason, score, status, created_at
    FROM revylia.opportunities
    """
    + _OPPORTUNITIES_WHERE
    + """
    ORDER BY score DESC, created_at DESC, id DESC
    LIMIT %(limit)s OFFSET %(offset)s
    """
)


def _opportunity_row(row) -> dict:
    return {
        "id": _sid(row["id"]),
        "patient_id": _sid(row["patient_id"]),
        "patient_name": row["patient_name"],
        "phone": row["phone"],
        "reason": row["reason"],
        "score": int(row["score"]),
        "status": row["status"],
        "created_at": _sts(row["created_at"]),
    }


def list_opportunities(
    conn,
    clinic_id: str,
    *,
    status: str | None = None,
    min_score: int | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[dict], int]:
    params = {"clinic_id": clinic_id, "status": status, "min_score": min_score}
    total = int(conn.execute(_OPPORTUNITIES_COUNT_SQL, params).fetchone()["total"])
    rows = conn.execute(
        _OPPORTUNITIES_SQL,
        {**params, "limit": clamp_limit(limit), "offset": clamp_offset(offset)},
    ).fetchall()
    return [_opportunity_row(row) for row in rows], total


# =====================================================================
# /escalations  (§5.4) — priority_rank se calcula con CASE en SQL
# =====================================================================

_ESCALATIONS_FROM = """
    FROM revylia.escalations e
    LEFT JOIN revylia.patients p
      ON p.id = e.patient_id AND p.clinic_id = e.clinic_id
    WHERE e.clinic_id = %(clinic_id)s
      AND (%(status)s::text IS NULL OR e.status = %(status)s)
      AND (%(priority)s::text IS NULL OR e.priority = %(priority)s)
"""

_ESCALATIONS_COUNT_SQL = "SELECT COUNT(*) AS total" + _ESCALATIONS_FROM
_ESCALATIONS_SQL = (
    """
    SELECT e.id, e.patient_id, p.name AS patient_name, e.reason, e.priority,
           CASE e.priority
               WHEN 'urgent' THEN 0
               WHEN 'high'   THEN 1
               WHEN 'medium' THEN 2
               WHEN 'low'    THEN 3
               ELSE 4
           END AS priority_rank,
           e.status, e.created_at
    """
    + _ESCALATIONS_FROM
    + """
    ORDER BY priority_rank ASC, e.created_at DESC, e.id DESC
    LIMIT %(limit)s OFFSET %(offset)s
    """
)


def _escalation_row(row) -> dict:
    return {
        "id": _sid(row["id"]),
        "patient_id": _sid(row["patient_id"]),
        "patient_name": row["patient_name"],
        "reason": row["reason"],
        "priority": row["priority"],
        "priority_rank": int(row["priority_rank"]),
        "status": row["status"],
        "created_at": _sts(row["created_at"]),
    }


def list_escalations(
    conn,
    clinic_id: str,
    *,
    status: str | None = None,
    priority: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[dict], int]:
    params = {"clinic_id": clinic_id, "status": status, "priority": priority}
    total = int(conn.execute(_ESCALATIONS_COUNT_SQL, params).fetchone()["total"])
    rows = conn.execute(
        _ESCALATIONS_SQL,
        {**params, "limit": clamp_limit(limit), "offset": clamp_offset(offset)},
    ).fetchall()
    return [_escalation_row(row) for row in rows], total


# =====================================================================
# /recovery
# =====================================================================

_RECOVERY_FROM = """
    FROM revylia.recovery_messages r
    JOIN revylia.patients p
      ON p.id = r.patient_id AND p.clinic_id = r.clinic_id
    WHERE r.clinic_id = %(clinic_id)s
      AND (%(status)s::text IS NULL OR r.status = %(status)s)
"""

_RECOVERY_COUNT_SQL = "SELECT COUNT(*) AS total" + _RECOVERY_FROM
_RECOVERY_SQL = (
    """
    SELECT r.id, r.patient_id, p.name AS patient_name, r.message,
           r.approval_required, r.status, r.created_at
    """
    + _RECOVERY_FROM
    + """
    ORDER BY r.created_at DESC, r.id DESC
    LIMIT %(limit)s OFFSET %(offset)s
    """
)


def _recovery_row(row) -> dict:
    return {
        "id": _sid(row["id"]),
        "patient_id": _sid(row["patient_id"]),
        "patient_name": row["patient_name"],
        "message": row["message"],
        "approval_required": bool(row["approval_required"]),
        "status": row["status"],
        "created_at": _sts(row["created_at"]),
    }


def list_recovery(
    conn,
    clinic_id: str,
    *,
    status: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[dict], int]:
    params = {"clinic_id": clinic_id, "status": status}
    total = int(conn.execute(_RECOVERY_COUNT_SQL, params).fetchone()["total"])
    rows = conn.execute(
        _RECOVERY_SQL,
        {**params, "limit": clamp_limit(limit), "offset": clamp_offset(offset)},
    ).fetchall()
    return [_recovery_row(row) for row in rows], total


# =====================================================================
# /events  (§5.5) — paginación por keyset sobre (received_at, id)
# =====================================================================

# `received_at` por sí solo NO es orden estable: la PK es `message_id TEXT`.
# Se pide una fila extra (limit + 1) para saber si hay página siguiente.
_EVENTS_SQL = """
    SELECT id, message_id, status, error_type, received_at,
           processed_at, response_text
    FROM revylia.whatsapp_inbound_events
    WHERE clinic_id = %(clinic_id)s
      AND (%(status)s::text IS NULL OR status = %(status)s)
      AND (%(cursor_ts)s::timestamptz IS NULL
           OR (received_at, id) < (%(cursor_ts)s::timestamptz, %(cursor_id)s::bigint))
    ORDER BY received_at DESC, id DESC
    LIMIT %(limit)s
"""


def encode_cursor(received_at: Any, row_id: Any) -> str:
    raw = f"{_sts(received_at)}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[str, int]:
    """Devuelve (timestamp ISO, id). Lanza ValueError si el cursor es basura."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        ts_text, _, id_text = raw.rpartition("|")
        if not ts_text:
            raise ValueError("cursor sin separador")
        return ts_text, int(id_text)
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise ValueError("Cursor de paginación inválido.") from exc


def _event_row(row) -> dict:
    # `id` y `from_number_hash` NO se exponen: `id` solo sirve para el
    # cursor y el hash del número nunca sale de la base (§5.5).
    return {
        "message_id": row["message_id"],
        "status": row["status"],
        "error_type": row["error_type"],
        "received_at": _sts(row["received_at"]),
        "processed_at": _sts(row["processed_at"]),
        "response_text": row["response_text"],
    }


def list_events(
    conn,
    clinic_id: str,
    *,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[list[dict], str | None]:
    limit = clamp_limit(limit)
    cursor_ts: str | None = None
    cursor_id: int | None = None
    if cursor:
        cursor_ts, cursor_id = decode_cursor(cursor)

    rows = conn.execute(
        _EVENTS_SQL,
        {
            "clinic_id": clinic_id,
            "status": status,
            "cursor_ts": cursor_ts,
            "cursor_id": cursor_id,
            "limit": limit + 1,
        },
    ).fetchall()

    rows = list(rows)
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = (
        encode_cursor(page[-1]["received_at"], page[-1]["id"])
        if has_more and page
        else None
    )
    return [_event_row(row) for row in page], next_cursor


# =====================================================================
# /catalog  (§5.6) — configuración versionada, no toca la base
# =====================================================================


def get_catalog() -> dict:
    """Copia profunda: nadie puede mutar CLINIC_KNOWLEDGE desde el panel."""
    return copy.deepcopy(CLINIC_KNOWLEDGE)
