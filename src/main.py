from fastapi import FastAPI, HTTPException

from src.core.config import get_settings
from src.core.logging import configure_logging
from src.database.connection import business_connection
from src.webhooks.whatsapp import router as whatsapp_router


configure_logging()
settings = get_settings()

app = FastAPI(
    title="Revylia WhatsApp Multiagent Gateway",
    version="0.2.0",
)
app.include_router(whatsapp_router, prefix="/api")


@app.get("/api/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "environment": settings.revylia_env,
        "graph_version": settings.graph_version,
        "model": settings.revylia_model,
        "langfuse_enabled": settings.langfuse_enabled,
        "whatsapp_send_enabled": settings.whatsapp_send_enabled,
        "database_configured": bool(settings.database_url),
    }


@app.get("/api/health/database", tags=["System"])
async def database_health():
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL no configurada")
    try:
        with business_connection(settings) as conn:
            row = conn.execute("SELECT 1 AS ok").fetchone()
        return {"status": "ok", "database": row["ok"] == 1}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {type(exc).__name__}",
        ) from exc
