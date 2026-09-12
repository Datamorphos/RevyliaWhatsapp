"""Verificación de JWT de Supabase por JWKS (§2 del contrato).

El backend verifica el token él mismo. Jamás confía en un header como
`X-User-Id`, `X-Panel-Enabled` o similares.

* Algoritmos asimétricos (ES256/RS256) con claves descargadas de
  `SUPABASE_JWKS_URL` y cacheadas en memoria. Nunca HS256 con secreto
  compartido.
* Se valida firma, `exp`, `iss` y `aud == "authenticated"`.
* La habilitación vive en `app_metadata.revylia_panel is True`.
  NUNCA en `user_metadata`: ese objeto lo puede editar el propio usuario
  desde el cliente, así que cualquier cuenta invitada podría
  autoautorizarse.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request

from src.panel.config import PanelSettings, get_panel_settings
from src.panel.errors import PanelError, forbidden, unauthorized, upstream_unavailable


ALLOWED_ALGORITHMS = ["ES256", "RS256"]
ENABLEMENT_CLAIM = "revylia_panel"

# `PyJWKClientConnectionError` existe desde PyJWT 2.8. Se resuelve de forma
# defensiva para no atarse a la versión exacta instalada.
_JWKSConnectionError = getattr(
    jwt.exceptions, "PyJWKClientConnectionError", jwt.PyJWKClientError
)

# --- Caché negativa de `kid` desconocidos ----------------------------------
# `PyJWKClient.get_signing_key_from_jwt` fuerza `get_signing_keys(refresh=True)`
# en cuanto el `kid` no está en caché, saltándose `lifespan` y `cache_jwk_set`.
# Como el `kid` se lee de la cabecera NO verificada del token, cualquiera puede
# provocar una descarga del JWKS por petición, sin credenciales: unas decenas
# de peticiones concurrentes con `kid` basura agotan el threadpool de Starlette
# (cada una espera hasta `timeout=10`) y además martillean Supabase desde la IP
# del backend.
#
# Recordar los `kid` que ya fallaron y rechazarlos sin red durante un rato corta
# la amplificación. El TTL es corto a propósito: una rotación legítima de claves
# se recupera sola en menos de un minuto.
_UNKNOWN_KID_TTL_SECONDS = 60.0
_UNKNOWN_KID_MAX_ENTRIES = 512
_unknown_kids: dict[str, float] = {}


def _kid_of(token: str) -> str | None:
    """`kid` de la cabecera SIN verificar. Solo se usa como clave de caché."""
    try:
        return jwt.get_unverified_header(token).get("kid")
    except jwt.InvalidTokenError:
        return None


def _kid_recently_failed(kid: str | None) -> bool:
    if not kid:
        return False
    expires_at = _unknown_kids.get(kid)
    if expires_at is None:
        return False
    if expires_at < time.monotonic():
        _unknown_kids.pop(kid, None)
        return False
    return True


def _remember_unknown_kid(kid: str | None) -> None:
    if not kid:
        return
    now = time.monotonic()
    if len(_unknown_kids) >= _UNKNOWN_KID_MAX_ENTRIES:
        # Purga perezosa: primero lo caducado; si no basta, se vacía entero.
        for key, expires_at in list(_unknown_kids.items()):
            if expires_at < now:
                _unknown_kids.pop(key, None)
        if len(_unknown_kids) >= _UNKNOWN_KID_MAX_ENTRIES:
            _unknown_kids.clear()
    _unknown_kids[kid] = now + _UNKNOWN_KID_TTL_SECONDS


def reset_unknown_kid_cache() -> None:
    """Limpia la caché negativa. Para los tests y para una rotación forzada."""
    _unknown_kids.clear()


@dataclass(frozen=True)
class PanelUser:
    sub: str
    email: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)


@lru_cache(maxsize=4)
def get_jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    """Cliente JWKS cacheado. `lru_cache` evita recrearlo en cada petición;
    `cache_jwk_set`/`cache_keys` evitan ir a la red en cada token."""
    return jwt.PyJWKClient(
        jwks_url,
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=600,
        timeout=10,
    )


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise unauthorized("Falta el encabezado Authorization.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthorized("El encabezado Authorization debe ser 'Bearer <token>'.")
    return token.strip()


def decode_token(token: str, settings: PanelSettings) -> dict[str, Any]:
    jwks_url = settings.jwks_url
    issuer = settings.jwt_issuer
    if not jwks_url or not issuer:
        # Fallo de configuración del servidor, no culpa del cliente.
        raise upstream_unavailable(
            "La verificación de identidad no está configurada en el servidor."
        )

    kid = _kid_of(token)
    if _kid_recently_failed(kid):
        # Ya se intentó hace poco y el JWKS no lo conocía. No se vuelve a la red.
        raise unauthorized("No se pudo verificar la firma del token.")

    try:
        signing_key = get_jwks_client(jwks_url).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ALLOWED_ALGORITHMS,
            audience=settings.jwt_audience,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except _JWKSConnectionError as exc:
        # No se pudo ALCANZAR el JWKS. Esto es un fallo de infraestructura, no
        # un problema de credenciales: devolverlo como 401 hacía que el
        # frontend mostrara "tu sesión expiró" a todo el personal durante un
        # corte de red, provocando cierres de sesión y reintentos en masa.
        # §4 exige `upstream_unavailable` (503) para fallos de upstream.
        raise upstream_unavailable(
            "No se pudo contactar con el proveedor de identidad."
        ) from exc
    except jwt.PyJWKClientError as exc:
        # El JWKS respondió pero no conoce este `kid`. Sí es culpa del cliente.
        _remember_unknown_kid(kid)
        raise unauthorized("No se pudo verificar la firma del token.") from exc
    except jwt.InvalidTokenError as exc:
        raise unauthorized("Token inválido o expirado.") from exc


def ensure_panel_enabled(claims: dict[str, Any]) -> None:
    """`app_metadata.revylia_panel` debe ser exactamente `True`.

    `user_metadata` se ignora a propósito, aunque traiga la misma clave.
    """
    app_metadata = claims.get("app_metadata")
    enabled = app_metadata.get(ENABLEMENT_CLAIM) if isinstance(app_metadata, dict) else None
    if enabled is not True:
        raise forbidden("Tu cuenta no está habilitada para el panel de Revylia.")


def build_user(claims: dict[str, Any]) -> PanelUser:
    sub = claims.get("sub")
    if not sub:
        raise unauthorized("El token no identifica a ningún usuario.")
    return PanelUser(sub=str(sub), email=claims.get("email"), claims=claims)


def require_panel_user(
    request: Request,
    settings: Annotated[PanelSettings, Depends(get_panel_settings)],
) -> PanelUser:
    """Dependencia de FastAPI: 401 sin token válido, 403 sin habilitación."""
    token = extract_bearer_token(request.headers.get("Authorization"))
    claims = decode_token(token, settings)
    ensure_panel_enabled(claims)
    return build_user(claims)


PanelUserDep = Annotated[PanelUser, Depends(require_panel_user)]

__all__ = [
    "ALLOWED_ALGORITHMS",
    "PanelError",
    "PanelUser",
    "PanelUserDep",
    "build_user",
    "decode_token",
    "ensure_panel_enabled",
    "extract_bearer_token",
    "get_jwks_client",
    "require_panel_user",
    "reset_unknown_kid_cache",
]
