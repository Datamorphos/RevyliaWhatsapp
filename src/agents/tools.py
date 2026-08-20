from typing import Any

from src.core.config import Settings, get_settings
from src.database.repository import ClinicRepository
from src.domain.knowledge import CLINIC_KNOWLEDGE
from src.observability.langfuse import LangfuseTracer


class ClinicTools:
    def __init__(
        self,
        repository: ClinicRepository,
        tracer: LangfuseTracer,
        settings: Settings | None = None,
    ):
        self.repository = repository
        self.tracer = tracer
        self.settings = settings or get_settings()

    def _run(self, name: str, inputs: dict[str, Any], fn):
        with self.tracer.tool(name, inputs) as observation:
            try:
                result = fn()
                if observation is not None:
                    observation.update(output=self.tracer.trace_payload(result))
                return result
            except Exception as exc:
                if observation is not None:
                    observation.update(
                        level="ERROR",
                        status_message=type(exc).__name__,
                        output={"error_type": type(exc).__name__},
                    )
                raise

    def list_available_slots(self, clinic_id: str, appointment_date: str) -> list[str]:
        return self._run(
            "list_available_slots",
            {"clinic_id": clinic_id, "appointment_date": appointment_date},
            lambda: self.repository.list_available_slots(clinic_id, appointment_date),
        )

    def create_appointment(self, clinic_id: str, **kwargs):
        inputs = {"clinic_id": clinic_id, **kwargs}
        return self._run(
            "create_appointment",
            inputs,
            lambda: self.repository.create_appointment(
                clinic_id,
                valid_services=set(CLINIC_KNOWLEDGE["services"].keys()),
                **kwargs,
            ),
        )

    def reschedule_appointment(self, clinic_id: str, **kwargs):
        return self._run(
            "reschedule_appointment",
            {"clinic_id": clinic_id, **kwargs},
            lambda: self.repository.reschedule_appointment(clinic_id, **kwargs),
        )

    def create_opportunity(self, clinic_id: str, **kwargs):
        return self._run(
            "create_opportunity",
            {"clinic_id": clinic_id, **kwargs},
            lambda: self.repository.create_opportunity(clinic_id, **kwargs),
        )

    def create_escalation(self, clinic_id: str, **kwargs):
        return self._run(
            "create_escalation",
            {"clinic_id": clinic_id, **kwargs},
            lambda: self.repository.create_escalation(clinic_id, **kwargs),
        )

    def list_recoverable_patients(self, clinic_id: str, **kwargs):
        return self._run(
            "list_recoverable_patients",
            {"clinic_id": clinic_id, **kwargs},
            lambda: self.repository.list_recoverable_patients(clinic_id, **kwargs),
        )

    def save_recovery_message(self, clinic_id: str, **kwargs):
        # Política de la V2: ningún texto del LLM puede habilitar envío automático.
        kwargs["approval_required"] = True
        return self._run(
            "save_recovery_message",
            {"clinic_id": clinic_id, **kwargs},
            lambda: self.repository.save_recovery_message(clinic_id, **kwargs),
        )
