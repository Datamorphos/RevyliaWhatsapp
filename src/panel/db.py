"""Conexión de SOLO LECTURA del panel (§9 del contrato).

Este módulo NO importa `src/database/connection.py` ni `ClinicRepository`:
esa clase tiene métodos de escritura y un `read_table()` que interpola el
nombre de tabla en un f-string. Aquí la imposibilidad de escribir es
estructural, no una lista de permitidos:

  1. El DSN es `PANEL_DATABASE_URL`, de un rol que solo tiene `GRANT
     SELECT`, no es dueño de las tablas y es `NOBYPASSRLS`
     (ver `migrations/003_panel_readonly.sql`). Esa es la garantía real.
  2. La sesión arranca con `default_transaction_read_only = on` (definido
     además a nivel de rol en 003, para que sobreviva al pooler).
  3. Ninguna función de `src/panel/` emite INSERT/UPDATE/DELETE.

`psycopg` se importa DENTRO de la función a propósito: así el paquete
`src.panel` se puede importar (y testear) en entornos donde el driver no
está instalado.
"""

from contextlib import contextmanager

from src.panel.config import PanelSettings, get_panel_settings


@contextmanager
def panel_connection(settings: PanelSettings | None = None):
    """Abre una conexión de solo lectura contra `PANEL_DATABASE_URL`."""
    import psycopg
    from psycopg.rows import dict_row

    settings = settings or get_panel_settings()
    dsn = settings.panel_database_url
    if not dsn:
        raise RuntimeError("PANEL_DATABASE_URL no está configurada")

    # autocommit=True: el panel nunca abre transacciones de escritura.
    # prepare_threshold=None: el Transaction Pooler de Supabase no soporta
    # prepared statements.
    conn = psycopg.Connection.connect(
        dsn,
        autocommit=True,
        prepare_threshold=None,
        row_factory=dict_row,
    )
    try:
        conn.execute("SET default_transaction_read_only = on")
        # Solo hace falta si el despliegue usó la variante multi-clínica de
        # 003 (políticas con `current_setting`). Con el literal fijo es
        # inofensivo. `SET` no admite parámetros; `set_config` sí.
        conn.execute(
            "SELECT set_config('revylia.clinic_id', %s, false)",
            (settings.revylia_clinic_id,),
        )
        yield conn
    finally:
        conn.close()
