import argparse
from pathlib import Path

from langgraph.checkpoint.postgres import PostgresSaver

from src.core.config import get_settings
from src.database.connection import business_connection, checkpoint_connection


ROOT = Path(__file__).resolve().parents[1]


def execute_sql_file(path: Path):
    settings = get_settings()
    sql = path.read_text(encoding="utf-8")
    with business_connection(settings, admin=True, autocommit=True) as conn:
        conn.execute(sql)


def setup_checkpoints():
    settings = get_settings()
    with checkpoint_connection(settings, admin=True) as conn:
        saver = PostgresSaver(conn)
        saver.setup()
        # Las tablas de LangGraph se crean en public. RLS sin políticas evita
        # acceso accidental desde anon/authenticated vía Data API.
        for table in [
            "checkpoint_migrations",
            "checkpoints",
            "checkpoint_blobs",
            "checkpoint_writes",
        ]:
            try:
                conn.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
            except Exception as exc:
                print(f"Aviso RLS {table}: {type(exc).__name__}: {exc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="Inserta datos demo idempotentes")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.admin_database_url:
        raise SystemExit("Configura DATABASE_URL_ADMIN o DATABASE_URL")

    print("1/3 Creando esquema/tablas Revylia...")
    execute_sql_file(ROOT / "migrations" / "001_business.sql")

    if args.seed:
        print("2/3 Insertando datos demo...")
        execute_sql_file(ROOT / "migrations" / "002_seed_demo.sql")
    else:
        print("2/3 Seed omitido")

    print("3/3 Creando/migrando tablas de PostgresSaver...")
    setup_checkpoints()
    print("Base de datos lista.")


if __name__ == "__main__":
    main()
