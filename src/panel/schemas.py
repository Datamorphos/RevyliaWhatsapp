"""Modelos de respuesta del panel.

§3: todo BIGINT (`id`, `patient_id`) viaja como `str`.
§4: la envoltura es `{"data": ..., "meta": {...}}` y el error es siempre
    `{"error": {"type": ..., "message": ...}}`.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


# ---------------------------------------------------------------------
# Envoltura (§4)
# ---------------------------------------------------------------------


class ListMeta(BaseModel):
    source: str
    filters: dict[str, Any] = Field(default_factory=dict)
    generated_at: str
    limit: int | None = None
    offset: int | None = None
    total: int | None = None
    next_cursor: str | None = None


class DetailMeta(BaseModel):
    source: str
    generated_at: str
    filters: dict[str, Any] | None = None
    pending_validation: bool | None = None


class ListResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: ListMeta


class DetailResponse(BaseModel, Generic[T]):
    data: T
    meta: DetailMeta


class ErrorBody(BaseModel):
    type: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# ---------------------------------------------------------------------
# Entidades (§5)
# ---------------------------------------------------------------------


class PatientOut(BaseModel):
    id: str
    name: str
    phone: str | None = None
    last_visit_date: str | None = None
    last_service: str | None = None
    status: str
    consent_marketing: bool
    notes: str | None = None
    created_at: str | None = None


class AppointmentOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str | None = None
    service: str
    appointment_date: str
    appointment_time: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None


class OpportunityOut(BaseModel):
    id: str
    patient_id: str | None = None
    patient_name: str | None = None
    phone: str | None = None
    reason: str
    score: int
    status: str
    created_at: str | None = None


class PatientDetailOut(PatientOut):
    appointments: list[AppointmentOut] = Field(default_factory=list)
    opportunities: list[OpportunityOut] = Field(default_factory=list)


class EscalationOut(BaseModel):
    id: str
    patient_id: str | None = None
    patient_name: str | None = None
    reason: str
    priority: str
    priority_rank: int
    status: str
    created_at: str | None = None


class RecoveryOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str | None = None
    message: str
    approval_required: bool
    status: str
    created_at: str | None = None


class EventOut(BaseModel):
    """`from_number_hash` NO se expone y no hay ruta de JOIN a un paciente:
    este módulo muestra estado de procesamiento, nunca una conversación."""

    message_id: str
    status: str
    error_type: str | None = None
    received_at: str | None = None
    processed_at: str | None = None
    response_text: str | None = None


class SlotOut(BaseModel):
    time: str
    available: bool


class AvailabilityOut(BaseModel):
    date: str
    # 0 = lunes ... 6 = domingo (`datetime.date.weekday()`).
    weekday: int
    is_open: bool
    slots: list[SlotOut] = Field(default_factory=list)


class SummaryMetric(BaseModel):
    value: int
    formula: str
