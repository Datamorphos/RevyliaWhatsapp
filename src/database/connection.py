from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from src.core.config import Settings, get_settings


def _connect(dsn: str, *, autocommit: bool) -> Connection:
    # Supabase Transaction Pooler no soporta prepared statements.
    return Connection.connect(
        dsn,
        autocommit=autocommit,
        prepare_threshold=None,
        row_factory=dict_row,
    )


@contextmanager
def business_connection(
    settings: Settings | None = None,
    *,
    admin: bool = False,
    autocommit: bool = False,
):
    settings = settings or get_settings()
    dsn = settings.admin_database_url if admin else settings.database_url
    if not dsn:
        name = "DATABASE_URL_ADMIN/DATABASE_URL" if admin else "DATABASE_URL"
        raise RuntimeError(f"{name} no está configurada")

    conn = _connect(dsn, autocommit=autocommit)
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def checkpoint_connection(settings: Settings | None = None, *, admin: bool = False):
    settings = settings or get_settings()
    dsn = settings.admin_database_url if admin else settings.database_url
    if not dsn:
        raise RuntimeError("DATABASE_URL no está configurada")

    # PostgresSaver requiere autocommit. prepare_threshold=None evita
    # prepared statements incompatibles con transaction pooling.
    conn = _connect(dsn, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()
