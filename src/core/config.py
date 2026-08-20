from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Revylia
    revylia_env: Literal["development", "staging", "production"] = "development"
    revylia_clinic_id: str = "clinica-sonrisas"
    revylia_channel: str = "whatsapp"
    revylia_model: str = "gemini-3.1-flash-lite"
    revylia_max_input_chars: int = 4000
    revylia_max_agent_steps: int = 2
    google_api_key: str | None = None

    graph_version: str = "0.4.0"
    prompt_version: str = "2026-08-20"
    llm_provider: str = "google_genai"

    # PostgreSQL / Supabase
    database_url: str | None = None
    database_url_admin: str | None = None

    # WhatsApp
    whatsapp_verify_token: str = "change-me"
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_send_enabled: bool = False
    whatsapp_allowed_from_numbers: str = ""
    meta_graph_api_version: str | None = None
    meta_app_secret: str | None = None
    verify_meta_signature: bool = False

    # Langfuse
    revylia_disable_langfuse: bool = True
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://us.cloud.langfuse.com"
    revylia_trace_sampling_rate: float = 1.0
    revylia_trace_content_mode: Literal["masked", "structure_only"] = "masked"
    langfuse_flush_each_request: bool = True

    @property
    def langfuse_enabled(self) -> bool:
        return (
            not self.revylia_disable_langfuse
            and bool(self.langfuse_public_key)
            and bool(self.langfuse_secret_key)
        )

    @property
    def admin_database_url(self) -> str | None:
        return self.database_url_admin or self.database_url

    @property
    def allowed_whatsapp_numbers(self) -> set[str]:
        return {
            "".join(ch for ch in item if ch.isdigit())
            for item in self.whatsapp_allowed_from_numbers.split(",")
            if item.strip()
        }

    def require_agent_runtime(self) -> None:
        missing = []
        if not self.database_url:
            missing.append("DATABASE_URL")
        if not self.google_api_key:
            missing.append("GOOGLE_API_KEY")
        if missing:
            raise RuntimeError(
                "Faltan variables para ejecutar los agentes: " + ", ".join(missing)
            )

    def require_whatsapp_send(self) -> None:
        if not self.whatsapp_send_enabled:
            return
        missing = []
        if not self.whatsapp_access_token:
            missing.append("WHATSAPP_ACCESS_TOKEN")
        if not self.meta_graph_api_version:
            missing.append("META_GRAPH_API_VERSION")
        if missing:
            raise RuntimeError(
                "Faltan variables para enviar por WhatsApp: " + ", ".join(missing)
            )

    def require_meta_signature(self) -> None:
        if self.verify_meta_signature and not self.meta_app_secret:
            raise RuntimeError(
                "META_APP_SECRET es obligatorio cuando VERIFY_META_SIGNATURE=true"
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not 0.0 <= settings.revylia_trace_sampling_rate <= 1.0:
        raise ValueError("REVYLIA_TRACE_SAMPLING_RATE debe estar entre 0 y 1")
    if settings.revylia_max_agent_steps < 1 or settings.revylia_max_agent_steps > 4:
        raise ValueError("REVYLIA_MAX_AGENT_STEPS debe estar entre 1 y 4")
    return settings
