"""Configuración del panel. Mismo patrón que `src/core/config.py`."""

import os
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

    @property
    def clinic_id_is_default(self) -> bool:
        """True si `REVYLIA_CLINIC_ID` no se fijó y se está usando el de demo.

        Importa porque `migrations/003_panel_readonly.sql` lleva el `clinic_id`
        incrustado como literal en las 7 políticas RLS. Si el valor efectivo
        aquí y el de las políticas no coinciden, la intersección es vacía y el
        panel devuelve **200 con `data: []` en todos los módulos**, sin ningún
        error: exactamente el fallo silencioso que 003 existe para evitar,
        reintroducido una capa más arriba.
        """
        return os.environ.get("REVYLIA_CLINIC_ID") in (None, "")

    def require_panel_runtime(self) -> None:
        missing = []
        if not self.panel_database_url:
            missing.append("PANEL_DATABASE_URL")
        if not self.jwks_url:
            missing.append("SUPABASE_JWKS_URL (o SUPABASE_URL)")
        if not self.jwt_issuer:
            missing.append("SUPABASE_JWT_ISSUER (o SUPABASE_URL)")
        if self.clinic_id_is_default:
            # Se exige explícito: heredar el literal de demo en silencio es
            # justo cómo se produce el panel vacío descrito arriba.
            missing.append(
                "REVYLIA_CLINIC_ID (debe coincidir EXACTAMENTE con el clinic_id "
                "de las políticas de migrations/003_panel_readonly.sql)"
            )
        if missing:
            raise RuntimeError(
                "Faltan variables para ejecutar el panel: " + ", ".join(missing)
            )

    def verify_clinic_exists(self, conn) -> None:
        """Falla ruidosamente si la clínica configurada no devuelve filas.

        Se llama al arrancar (`src/panel/app.py`). Cubre los dos modos de fallo
        que producen un panel vacío sin error: un `REVYLIA_CLINIC_ID` que no
        existe, y unas políticas RLS que filtran por otro `clinic_id`. En ambos
        casos este SELECT devuelve cero filas y el proceso no arranca, en vez
        de servir siete tablas vacías y trece KPIs en cero.
        """
        row = conn.execute(
            "SELECT 1 AS ok FROM revylia.clinics WHERE id = %s",
            (self.revylia_clinic_id,),
        ).fetchone()
        if not row:
            raise RuntimeError(
                f"La clínica '{self.revylia_clinic_id}' no devuelve filas con la "
                "credencial de solo lectura. Revisa REVYLIA_CLINIC_ID y el "
                "clinic_id de las políticas RLS de migrations/003_panel_readonly.sql: "
                "si no coinciden, el panel se vería vacío sin ningún error."
            )


@lru_cache
def get_panel_settings() -> PanelSettings:
    return PanelSettings()
