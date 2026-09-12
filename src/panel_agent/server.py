"""Exposición del copiloto del panel por AG-UI (§6 del contrato).

Generación v2 en ambos lados: aquí `ag_ui_langgraph.add_langgraph_fastapi_endpoint`
con `copilotkit.LangGraphAGUIAgent`; en Next.js `@copilotkit/runtime/v2` con
`HttpAgent` de `@ag-ui/client`.

NO se usa la API v1 (`CopilotKitRemoteEndpoint`, `LangGraphAgent`,
`copilotkit.integrations.fastapi.add_fastapi_endpoint`): mezclar generaciones
rompe la integración.

Despliegue separado: esta app es autónoma, igual que `src/panel/app.py`.
`src/main.py` (el gateway de WhatsApp) no se toca.

    8000  gateway de WhatsApp   uvicorn src.main:app
    8001  API del panel         uvicorn src.panel.app:app
    8123  copiloto AG-UI        uvicorn src.panel_agent.server:app   <- este archivo

--------------------------------------------------------------------------
AUTENTICACIÓN — corrección de un fallo crítico
--------------------------------------------------------------------------
La primera versión montaba el endpoint AG-UI **sin ninguna dependencia de
FastAPI**. Como las herramientas del grafo abren su propia conexión y leen toda
la clínica, cualquiera que alcanzara este puerto obtenía nombres, teléfonos y
notas de pacientes sin credencial alguna. La API hermana (`src/panel/router.py`)
sí verifica el JWT por JWKS; este proceso era la puerta sin cerradura al mismo
dato.

Ahora TODA petición bajo `AGENT_PATH` pasa por el mismo control que la API:
firma por JWKS, `exp`/`iss`/`aud`, y `app_metadata.revylia_panel is True`
(nunca `user_metadata`). Se implementa como middleware HTTP y no como
`Depends(...)` porque `add_langgraph_fastapi_endpoint` registra la ruta por su
cuenta y no admite inyectar dependencias.

El proxy de Next.js (`web/app/api/copilotkit/route.ts`) reenvía el
`Authorization: Bearer <token>` de la sesión de Supabase.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.panel.auth import (
    build_user,
    decode_token,
    ensure_panel_enabled,
    extract_bearer_token,
)
from src.panel.config import get_panel_settings
from src.panel.errors import PanelError


logger = logging.getLogger(__name__)

AGENT_NAME = "revylia_panel"
AGENT_PATH = "/agent/revylia_panel"
AGENT_DESCRIPTION = (
    "Copiloto de solo lectura del panel Revylia: consulta pacientes, citas, "
    "disponibilidad, oportunidades, escalamientos, recuperación, eventos de "
    "WhatsApp y el catálogo de la clínica. No realiza ninguna escritura."
)

_STATUS_BY_ERROR = {
    "unauthorized": 401,
    "forbidden": 403,
    "upstream_unavailable": 503,
}


def _error(status: int, error_type: str, message: str) -> JSONResponse:
    """Mismo sobre de error que §4. Nunca traza ni SQL."""
    return JSONResponse(
        status_code=status,
        content={"error": {"type": error_type, "message": message}},
    )


def install_agent_auth(app: FastAPI, *, path: str = AGENT_PATH) -> None:
    """Exige un JWT válido y habilitado en toda petición bajo `path`."""

    @app.middleware("http")
    async def _require_panel_user(request: Request, call_next):
        if not request.url.path.startswith(path):
            return await call_next(request)

        settings = get_panel_settings()
        try:
            token = extract_bearer_token(request.headers.get("authorization"))
            claims = decode_token(token, settings)
            ensure_panel_enabled(claims)
            request.state.panel_user = build_user(claims)
        except PanelError as exc:
            # No se registra el token ni las cabeceras.
            logger.warning("Acceso denegado al copiloto: %s", exc.error_type)
            return _error(
                _STATUS_BY_ERROR.get(exc.error_type, 401), exc.error_type, str(exc)
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fallo verificando credenciales del copiloto")
            return _error(
                401, "unauthorized", "No se pudo verificar la sesión."
            )

        return await call_next(request)


def register_panel_agent(app: FastAPI, *, graph=None, path: str = AGENT_PATH) -> FastAPI:
    """Monta el agente AG-UI sobre `app` en `path`. `AGENT_URL` debe apuntar aquí.

    Importa `ag_ui_langgraph`/`copilotkit` y construye el grafo **dentro** de la
    función, no al importar el módulo: `build_panel_graph()` exige
    `GOOGLE_API_KEY` y hacerlo a nivel de módulo rompía el simple `import` de
    este archivo (y con él cualquier test o herramienta que lo tocara).
    """
    from ag_ui_langgraph import add_langgraph_fastapi_endpoint
    from copilotkit import LangGraphAGUIAgent

    from src.panel_agent.graph import build_panel_graph

    install_agent_auth(app, path=path)
    add_langgraph_fastapi_endpoint(
        app=app,
        agent=LangGraphAGUIAgent(
            name=AGENT_NAME,
            description=AGENT_DESCRIPTION,
            graph=graph if graph is not None else build_panel_graph(),
        ),
        path=path,
    )
    return app


def create_app() -> FastAPI:
    """Construye la app del copiloto. Fábrica, para no ejecutar nada al importar."""
    app = FastAPI(title="Revylia Panel Copilot")
    register_panel_agent(app)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "agent": AGENT_NAME, "path": AGENT_PATH}

    return app


# `uvicorn src.panel_agent.server:app` sigue funcionando; el coste de construir
# el grafo se paga aquí y no en un `import` suelto del módulo.
def __getattr__(name: str):
    if name == "app":
        return create_app()
    raise AttributeError(name)
