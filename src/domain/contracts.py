from typing import Literal

from pydantic import BaseModel, Field, field_validator


AgentName = Literal["reception", "agenda", "recovery", "clinic_brain"]


class RouteDecision(BaseModel):
    agents: list[AgentName] = Field(
        description="Uno o máximo dos agentes, en el orden en que deben ejecutarse."
    )
    reason: str = Field(description="Justificación breve de la ruta.")

    @field_validator("agents")
    @classmethod
    def validate_agents(cls, value):
        unique = list(dict.fromkeys(value))
        return unique[:2] or ["reception"]


class ReceptionDecision(BaseModel):
    intent: Literal[
        "greeting", "lead", "complaint", "clinical_risk", "general", "human_request"
    ]
    reply: str
    patient_name: str | None = None
    phone: str | None = None
    create_opportunity: bool = False
    opportunity_reason: str | None = None
    lead_score: int = Field(default=50, ge=0, le=100)
    escalate: bool = False
    escalation_priority: Literal["low", "medium", "high", "urgent"] = "medium"
    escalation_reason: str | None = None


class AgendaDecision(BaseModel):
    action: Literal["check", "create", "reschedule", "clarify"]
    reply: str
    patient_name: str | None = None
    phone: str | None = None
    service: str | None = None
    appointment_date: str | None = Field(default=None, description="Fecha ISO YYYY-MM-DD")
    appointment_time: str | None = Field(default=None, description="Hora HH:MM, formato 24h")


class RecoveryDecision(BaseModel):
    action: Literal["list", "draft", "clarify"]
    reply: str
    days_inactive: int = Field(default=180, ge=30, le=2000)
    limit: int = Field(default=5, ge=1, le=20)
    approval_required: bool = True
    campaign_tone: Literal["warm", "professional", "brief"] = "warm"
