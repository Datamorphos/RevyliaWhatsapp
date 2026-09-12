"""Configuración del panel. Mismo patrón que `src/core/config.py`."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


# El JWT de Supabase para un usuario autenticado siempre lleva esta audiencia.
SUPABASE_AUDIENCE = "authenticated"


class PanelSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # DSN PROPIO de solo lectura. Jamás se reutiliza DATABASE_URL: ese rol
    # es dueño de las tablas, salta RLS y puede escribir.
    panel_database_url: str | None = None

    # Se reutiliza REVYLIA_CLINIC_ID: única fuente de `clinic_id` del
    # servidor. Nunca llega desde la petición del cliente.
    revylia_clinic_id: str = "clinica-sonrisas"

    supabase_url: str | None = None
    supabase_jwt_issuer: str | None = None
    supabase_jwks_url: str | None = None

    @property
    def jwt_issuer(self) -> str | None:
        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1"
        return None

    @property
    def jwks_url(self) -> str | None:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return None

    @property
    def jwt_audience(self) -> str:
        return SUPABASE_AUDIENCE

    def require_panel_runtime(self) -> None:
        missing = []
        if not self.panel_database_url:
            missing.append("PANEL_DATABASE_URL")
        if not self.jwks_url:
            missing.append("SUPABASE_JWKS_URL (o SUPABASE_URL)")
        if not self.jwt_issuer:
            missing.append("SUPABASE_JWT_ISSUER (o SUPABASE_URL)")
        if missing:
            raise RuntimeError(
                "Faltan variables para ejecutar el panel: " + ", ".join(missing)
            )


@lru_cache
def get_panel_settings() -> PanelSettings:
    return PanelSettings()
