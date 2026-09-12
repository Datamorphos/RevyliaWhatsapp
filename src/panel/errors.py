"""Error único del panel. La envoltura de §4 se aplica en `router.py`.

Se evita `HTTPException` a propósito: produce `{"detail": ...}`, que NO es
la forma del contrato, y corregirlo requeriría un `exception_handler` en
`src/main.py`, archivo fuera del alcance de escritura de este agente.
"""

# Tipos permitidos por §4 del contrato.
ERROR_TYPES = frozenset(
    {
        "unauthorized",
        "forbidden",
        "not_found",
        "validation_error",
        "upstream_unavailable",
    }
)


class PanelError(Exception):
    """Error de negocio del panel, ya traducido a la forma del contrato."""

    def __init__(self, status_code: int, error_type: str, message: str) -> None:
        if error_type not in ERROR_TYPES:
            raise ValueError(f"Tipo de error no permitido por el contrato: {error_type}")
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.message = message


def unauthorized(message: str = "Falta un token de acceso válido.") -> PanelError:
    return PanelError(401, "unauthorized", message)


def forbidden(message: str = "Tu cuenta no tiene acceso al panel.") -> PanelError:
    return PanelError(403, "forbidden", message)


def not_found(message: str = "No se encontró el recurso solicitado.") -> PanelError:
    return PanelError(404, "not_found", message)


def validation_error(message: str) -> PanelError:
    return PanelError(400, "validation_error", message)


def upstream_unavailable(
    message: str = "No se pudo consultar la base de datos en este momento.",
) -> PanelError:
    return PanelError(503, "upstream_unavailable", message)
