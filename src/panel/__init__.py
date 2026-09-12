"""API de solo lectura del panel Revylia.

Este paquete NUNCA escribe en la base de datos. No importa
`ClinicRepository` ni `src/database/connection.py`: tiene su propio helper
de conexión atado al DSN de solo lectura (`PANEL_DATABASE_URL`).
"""
