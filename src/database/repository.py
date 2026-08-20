from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Any

from psycopg.errors import UniqueViolation

from src.core.config import Settings, get_settings
from src.core.security import normalize_phone, stable_hash
from src.database.connection import business_connection


BOGOTA_TIMEZONE = "America/Bogota"
BOGOTA_TZ = ZoneInfo(BOGOTA_TIMEZONE)


def _today_bogota() -> date:
    return datetime.now(BOGOTA_TZ).date()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def _row(row) -> dict[str, Any] | None:
    return _json_safe(dict(row)) if row else None


class ClinicRepository:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def find_patient(
        self,
        clinic_id: str,
        *,
        name: str | None = None,
        phone: str | None = None,
    ) -> dict[str, Any] | None:
        phone = normalize_phone(phone)
        with business_connection(self.settings) as conn:
            if phone:
                row = conn.execute(
                    """
                    SELECT * FROM revylia.patients
                    WHERE clinic_id = %s AND phone = %s
                    LIMIT 1
                    """,
                    (clinic_id, phone),
                ).fetchone()
                if row:
                    return _row(row)

            if name:
                row = conn.execute(
                    """
                    SELECT * FROM revylia.patients
                    WHERE clinic_id = %s AND name ILIKE %s
                    ORDER BY id
                    LIMIT 1
                    """,
                    (clinic_id, f"%{name.strip()}%"),
                ).fetchone()
                if row:
                    return _row(row)
        return None

    def get_or_create_patient(self, clinic_id: str, name: str, phone: str) -> dict[str, Any]:
        phone = normalize_phone(phone)
        if not name or not phone:
            raise ValueError("Se requieren nombre y teléfono para localizar o crear al paciente.")

        with business_connection(self.settings) as conn:
            row = conn.execute(
                """
                INSERT INTO revylia.patients
                    (clinic_id, name, phone, status, consent_marketing, notes)
                VALUES (%s, %s, %s, 'active', false, 'Creado desde conversación de Revylia')
                ON CONFLICT (clinic_id, phone)
                DO UPDATE SET name = EXCLUDED.name
                RETURNING *
                """,
                (clinic_id, name.strip(), phone),
            ).fetchone()
            return _row(row)

    def list_available_slots(self, clinic_id: str, appointment_date: str) -> list[str]:
        parsed = date.fromisoformat(appointment_date)
        weekday = parsed.weekday()
        if weekday == 6:
            return []

        end_hour = 12 if weekday == 5 else 17
        candidate_slots = [f"{hour:02d}:00" for hour in range(8, end_hour)]

        with business_connection(self.settings) as conn:
            rows = conn.execute(
                """
                SELECT appointment_time
                FROM revylia.appointments
                WHERE clinic_id = %s
                  AND appointment_date = %s
                  AND status IN ('confirmed', 'pending')
                """,
                (clinic_id, parsed),
            ).fetchall()

        booked = {
            row["appointment_time"].strftime("%H:%M")
            if hasattr(row["appointment_time"], "strftime")
            else str(row["appointment_time"])[:5]
            for row in rows
        }
        return [slot for slot in candidate_slots if slot not in booked]

    def create_appointment(
        self,
        clinic_id: str,
        *,
        patient_name: str,
        phone: str,
        service: str,
        appointment_date: str,
        appointment_time: str,
        valid_services: set[str],
    ) -> dict[str, Any]:
        if service not in valid_services:
            raise ValueError(f"Servicio no reconocido: {service}")

        parsed_date = date.fromisoformat(appointment_date)
        if parsed_date < _today_bogota():
            raise ValueError("No se puede crear una cita en una fecha pasada.")

        available = self.list_available_slots(clinic_id, appointment_date)
        if appointment_time not in available:
            raise ValueError(
                f"El horario {appointment_time} no está disponible. "
                f"Opciones: {', '.join(available[:6]) or 'sin disponibilidad'}"
            )

        patient = self.get_or_create_patient(clinic_id, patient_name, phone)

        try:
            with business_connection(self.settings) as conn:
                row = conn.execute(
                    """
                    INSERT INTO revylia.appointments
                        (clinic_id, patient_id, service, appointment_date,
                         appointment_time, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, 'confirmed', now())
                    RETURNING *
                    """,
                    (
                        clinic_id,
                        patient["id"],
                        service,
                        parsed_date,
                        appointment_time,
                    ),
                ).fetchone()
                appointment = _row(row)
                appointment["patient_name"] = patient["name"]
                appointment["phone"] = patient["phone"]
                return appointment
        except UniqueViolation as exc:
            raise ValueError("Ese horario acaba de ser ocupado. Consulta disponibilidad nuevamente.") from exc

    def reschedule_appointment(
        self,
        clinic_id: str,
        *,
        patient_name: str,
        new_date: str,
        new_time: str,
    ) -> dict[str, Any]:
        patient = self.find_patient(clinic_id, name=patient_name)
        if not patient:
            raise ValueError("No encontré al paciente.")

        available = self.list_available_slots(clinic_id, new_date)
        if new_time not in available:
            raise ValueError(
                f"El horario {new_time} no está disponible. "
                f"Opciones: {', '.join(available[:6]) or 'sin disponibilidad'}"
            )

        with business_connection(self.settings) as conn:
            current = conn.execute(
                """
                SELECT * FROM revylia.appointments
                WHERE clinic_id = %s
                  AND patient_id = %s
                  AND status IN ('confirmed', 'pending')
                  AND appointment_date >= CURRENT_DATE
                ORDER BY appointment_date, appointment_time
                LIMIT 1
                """,
                (clinic_id, patient["id"]),
            ).fetchone()

            if not current:
                raise ValueError("El paciente no tiene una cita futura activa.")

            try:
                updated = conn.execute(
                    """
                    UPDATE revylia.appointments
                    SET appointment_date = %s, appointment_time = %s, updated_at = now()
                    WHERE id = %s AND clinic_id = %s
                    RETURNING *
                    """,
                    (date.fromisoformat(new_date), new_time, current["id"], clinic_id),
                ).fetchone()
            except UniqueViolation as exc:
                raise ValueError("Ese horario acaba de ser ocupado. Consulta disponibilidad nuevamente.") from exc

            result = _row(updated)
            result["patient_name"] = patient["name"]
            result["phone"] = patient["phone"]
            return result

    def create_opportunity(
        self,
        clinic_id: str,
        *,
        patient_name: str | None,
        phone: str | None,
        reason: str,
        score: int = 60,
    ) -> dict[str, Any]:
        patient = self.find_patient(clinic_id, name=patient_name, phone=phone)
        score = max(0, min(int(score), 100))
        with business_connection(self.settings) as conn:
            row = conn.execute(
                """
                INSERT INTO revylia.opportunities
                    (clinic_id, patient_id, patient_name, phone, reason,
                     score, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'open', now())
                RETURNING *
                """,
                (
                    clinic_id,
                    patient["id"] if patient else None,
                    patient_name,
                    normalize_phone(phone),
                    reason,
                    score,
                ),
            ).fetchone()
            return _row(row)

    def create_escalation(
        self,
        clinic_id: str,
        *,
        reason: str,
        priority: str = "high",
        patient_name: str | None = None,
        phone: str | None = None,
    ) -> dict[str, Any]:
        patient = self.find_patient(clinic_id, name=patient_name, phone=phone)
        if priority not in {"low", "medium", "high", "urgent"}:
            priority = "high"

        with business_connection(self.settings) as conn:
            row = conn.execute(
                """
                INSERT INTO revylia.escalations
                    (clinic_id, patient_id, reason, priority, status, created_at)
                VALUES (%s, %s, %s, %s, 'pending', now())
                RETURNING *
                """,
                (
                    clinic_id,
                    patient["id"] if patient else None,
                    reason,
                    priority,
                ),
            ).fetchone()
            return _row(row)

    def list_recoverable_patients(
        self,
        clinic_id: str,
        *,
        days_inactive: int = 180,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        cutoff = _today_bogota() - timedelta(days=days_inactive)
        with business_connection(self.settings) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM revylia.patients
                WHERE clinic_id = %s
                  AND consent_marketing = true
                  AND last_visit_date IS NOT NULL
                  AND last_visit_date <= %s
                  AND status = 'inactive'
                ORDER BY last_visit_date ASC
                LIMIT %s
                """,
                (clinic_id, cutoff, limit),
            ).fetchall()
            return [_row(row) for row in rows]

    def save_recovery_message(
        self,
        clinic_id: str,
        *,
        patient_id: int,
        message: str,
        approval_required: bool = True,
    ) -> dict[str, Any]:
        with business_connection(self.settings) as conn:
            row = conn.execute(
                """
                INSERT INTO revylia.recovery_messages
                    (clinic_id, patient_id, message, approval_required,
                     status, created_at)
                VALUES (%s, %s, %s, %s, %s, now())
                RETURNING *
                """,
                (
                    clinic_id,
                    patient_id,
                    message,
                    approval_required,
                    "draft" if approval_required else "approved",
                ),
            ).fetchone()
            return _row(row)

    def database_summary(self, clinic_id: str) -> dict[str, int]:
        tables = [
            "patients",
            "appointments",
            "opportunities",
            "escalations",
            "recovery_messages",
        ]
        result = {}
        with business_connection(self.settings) as conn:
            for table in tables:
                row = conn.execute(
                    f"SELECT COUNT(*) AS total FROM revylia.{table} WHERE clinic_id = %s",
                    (clinic_id,),
                ).fetchone()
                result[table] = int(row["total"])
        return result

    def read_table(self, clinic_id: str, table: str, limit: int = 20) -> list[dict[str, Any]]:
        allowed = {
            "patients",
            "appointments",
            "opportunities",
            "escalations",
            "recovery_messages",
            "whatsapp_inbound_events",
        }
        if table not in allowed:
            raise ValueError(f"Tabla no permitida: {table}")
        order_column = {
            "patients": "id",
            "whatsapp_inbound_events": "received_at",
        }.get(table, "created_at")
        with business_connection(self.settings) as conn:
            rows = conn.execute(
                f"SELECT * FROM revylia.{table} WHERE clinic_id = %s "
                f"ORDER BY {order_column} DESC NULLS LAST, id DESC LIMIT %s",
                (clinic_id, limit),
            ).fetchall()
            return [_row(row) for row in rows]


class WhatsAppEventRepository:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def claim(self, clinic_id: str, message_id: str, from_number: str) -> bool:
        with business_connection(self.settings) as conn:
            row = conn.execute(
                """
                INSERT INTO revylia.whatsapp_inbound_events
                    (message_id, clinic_id, from_number_hash, status, received_at)
                VALUES (%s, %s, %s, 'processing', now())
                ON CONFLICT (message_id) DO NOTHING
                RETURNING message_id
                """,
                (message_id, clinic_id, stable_hash(from_number)),
            ).fetchone()
            return row is not None

    def mark_completed(self, message_id: str, response_text: str) -> None:
        with business_connection(self.settings) as conn:
            conn.execute(
                """
                UPDATE revylia.whatsapp_inbound_events
                SET status = 'completed', response_text = %s, processed_at = now()
                WHERE message_id = %s
                """,
                (response_text, message_id),
            )

    def mark_failed(self, message_id: str, error_type: str) -> None:
        with business_connection(self.settings) as conn:
            conn.execute(
                """
                UPDATE revylia.whatsapp_inbound_events
                SET status = 'failed', error_type = %s, processed_at = now()
                WHERE message_id = %s
                """,
                (error_type[:120], message_id),
            )
