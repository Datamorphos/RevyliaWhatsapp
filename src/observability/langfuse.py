import re
from contextlib import contextmanager
from typing import Any

from src.core.config import Settings, get_settings


SENSITIVE_KEYS = {
    "content", "messages", "reply", "final_response", "patient_name", "phone",
    "name", "notes", "reason", "message", "prompt", "system_prompt",
    "opportunity_reason", "escalation_reason", "user_text", "history",
    "id", "patient_id", "appointment_id", "opportunity_id", "escalation_id",
    "document", "email", "address", "birth_date", "response_text",
}
SAFE_STRING_KEYS = {
    "environment", "graph_version", "prompt_version", "provider", "model",
    "channel", "agent", "agent_name", "route", "status", "type",
    "operation", "action", "tool", "run_type", "error_type", "metric",
    "tenant_hash", "thread_hash", "request_id", "trace_id",
    "executed_agents", "action_types", "trajectory", "safety_flags",
}

PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?57[\s-]?)?3\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
LONG_ID_PATTERN = re.compile(r"\b\d{6,15}\b")
UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def mask_text(value: str) -> str:
    value = PHONE_PATTERN.sub("<phone>", value)
    value = EMAIL_PATTERN.sub("<email>", value)
    value = UUID_PATTERN.sub("<uuid>", value)
    value = LONG_ID_PATTERN.sub("<document-or-id>", value)
    return value


def masked_payload(value: Any, depth: int = 12) -> Any:
    if depth <= 0:
        return "<max-depth>"
    if isinstance(value, dict):
        return {
            key: (
                "<redacted>"
                if str(key).lower() in SENSITIVE_KEYS
                else masked_payload(item, depth - 1)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [masked_payload(item, depth - 1) for item in value]
    if isinstance(value, str):
        return mask_text(value)
    return value


def structure_only_payload(value: Any, depth: int = 12, parent_key: str | None = None) -> Any:
    if depth <= 0:
        return "<max-depth>"
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in SENSITIVE_KEYS:
                cleaned[key] = "<redacted>"
            else:
                cleaned[key] = structure_only_payload(item, depth - 1, normalized_key)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [structure_only_payload(item, depth - 1, parent_key) for item in value]
    if isinstance(value, str):
        return value if parent_key in SAFE_STRING_KEYS else "<redacted-text>"
    return value


class LangfuseTracer:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = None
        self.handler = None

        if self.settings.langfuse_enabled:
            from langfuse import Langfuse
            from langfuse.langchain import CallbackHandler

            self.client = Langfuse(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key,
                base_url=self.settings.langfuse_base_url,
                environment=self.settings.revylia_env,
                release=self.settings.graph_version,
                sample_rate=self.settings.revylia_trace_sampling_rate,
                mask=self.trace_payload,
            )
            self.handler = CallbackHandler(public_key=self.settings.langfuse_public_key)

    @property
    def enabled(self) -> bool:
        return self.client is not None and self.handler is not None

    def trace_payload(self, value: Any) -> Any:
        if self.settings.revylia_trace_content_mode == "structure_only":
            return structure_only_payload(value)
        return masked_payload(value)

    @contextmanager
    def tool(self, name: str, inputs: dict[str, Any]):
        if not self.enabled:
            yield None
            return
        with self.client.start_as_current_observation(
            as_type="tool",
            name=f"tool.{name}",
            input=self.trace_payload(inputs),
            metadata={
                "tool": name,
                "environment": self.settings.revylia_env,
                "graph_version": self.settings.graph_version,
            },
        ) as observation:
            yield observation

    def flush(self) -> None:
        if self.enabled and self.settings.langfuse_flush_each_request:
            self.client.flush()
