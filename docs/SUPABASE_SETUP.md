# Supabase

## URLs recomendadas

- `DATABASE_URL`: Transaction Pooler para Vercel/serverless.
- `DATABASE_URL_ADMIN`: Direct o Session Pooler para setup/migraciones.

La aplicación usa `prepare_threshold=None` porque los transaction poolers no soportan prepared statements de sesión.

## Setup

```bash
python scripts/setup_database.py --seed
```

## Seguridad de esta demo

Las tablas tienen RLS habilitado y no se crean políticas para `anon` o `authenticated`. La aplicación se conecta directamente a PostgreSQL desde backend.

No coloques la cadena de conexión de PostgreSQL en frontend, JavaScript público ni aplicación móvil.
