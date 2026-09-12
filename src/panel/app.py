"""Aplicación FastAPI del panel de consulta (solo lectura).

**Despliegue separado del gateway, a propósito.**

El plan (`PLAN_APPWEB_REVYLIA.md`, "despliegue separado del gateway") pide que
el panel no comparta despliegue con el webhook de WhatsApp. Por eso el router
del panel NO se monta en `src/main.py`: esta es una aplicación autónoma, con su
propio proceso, su propio puerto y su propia credencial de base de datos
(`PANEL_DATABASE_URL`, un rol de solo lectura sin propiedad de tablas).

Consecuencias deseadas de la separación:

- Un fallo, un despliegue o un reinicio del panel no afecta a la recepción de
  mensajes de WhatsApp, que es la ruta crítica del negocio.
- El gateway sigue usando `DATABASE_URL` (rol con escritura); el panel usa
  `PANEL_DATABASE_URL` (rol de solo lectura). Nunca comparten credencial.
- `src/main.py` queda intacto: cero riesgo de regresión sobre el gateway.

Puertos canónicos en desarrollo (ver `DEMO.md`):

    8000  gateway de WhatsApp      uvicorn src.main:app
    8001  API del panel            uvicorn src.panel.app:app       <- este archivo
    8123  copiloto AG-UI           uvicorn src.panel_agent.server:app

Arranque:

    uvicorn src.panel.app:app --port 8001

El formato de error de §4 y la envoltura de §4 los aplica `PanelRoute`
(`src/panel/router.py`), así que aquí no hace falta registrar
`exception_handler`: basta con incluir el router.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.logging import configure_logging
from src.panel.config import get_panel_settings
from src.panel.router import router as panel_router


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Comprobación de arranque: falla ruidosamente antes de servir nada.

    Sin esto, un `REVYLIA_CLINIC_ID` equivocado o unas políticas RLS que
    filtren por otro `clinic_id` producen un panel que responde `200` con
    `data: []` en los siete módulos y trece KPIs en cero — indistinguible de
    una clínica sin actividad. Es preferible no arrancar.

    Si no hay `PANEL_DATABASE_URL` se omite la comprobación y se avisa: así el
    módulo sigue siendo importable en desarrollo y en los tests.
    """
    settings = get_panel_settings()
    if not settings.panel_database_url:
        logger.warning(
            "PANEL_DATABASE_URL no está configurada: se omite la verificación "
            "de clínica. La API responderá 503 en las rutas que tocan datos."
        )
    else:
        from src.panel.db import panel_connection

        with panel_connection(settings) as conn:
            settings.verify_clinic_exists(conn)
        logger.info(
            "Panel listo para la clínica '%s'.", settings.revylia_clinic_id
        )
    yield

app = FastAPI(
    title="Revylia Panel API (solo lectura)",
    version="0.1.0",
    description=(
        "API de consulta del panel interno de Revylia. Solo lectura: ni esta "
        "API, ni el copiloto, ni la credencial SQL pueden escribir."
    ),
    lifespan=lifespan,
)

app.include_router(panel_router)


@app.get("/health", tags=["System"])
def health() -> dict:
    """Salud del panel. No toca la base de datos ni expone secretos."""
    settings = get_panel_settings()
    return {
        "status": "ok",
        "service": "revylia-panel-api",
        "clinic_id": settings.revylia_clinic_id,
        "database_configured": bool(settings.panel_database_url),
        "auth_configured": bool(settings.jwks_url),
    }
