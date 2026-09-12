-- =====================================================================
-- 003_panel_readonly.sql — Rol de SOLO LECTURA para el panel Revylia
-- =====================================================================
--
-- ESTE ARCHIVO NO SE EJECUTA AUTOMÁTICAMENTE.
-- Lo ejecuta UNA PERSONA con credenciales de administrador de la base
-- (owner del esquema `revylia` o superusuario), a mano, una sola vez.
-- Ni la aplicación, ni el panel, ni ningún agente lo ejecutan.
--
-- POR QUÉ EXISTE (lee esto antes de tocar nada):
-- `001_business.sql` hace `ENABLE ROW LEVEL SECURITY` en las 7 tablas y
-- NO define NINGUNA política. El gateway actual funciona solo porque se
-- conecta con el rol DUEÑO de las tablas, y los dueños saltan RLS.
-- Un rol nuevo de solo lectura con `GRANT SELECT` pero sin políticas
-- recibiría CERO FILAS en todas las consultas, SIN ERROR: el panel se
-- vería "sin datos" en todos los módulos y nadie sabría por qué.
-- Por eso aquí se crean políticas `FOR SELECT` explícitas para el rol.
--
-- ANTES DE EJECUTAR, SUSTITUYE:
--   1. 'clinica-sonrisas'  -> el valor real de REVYLIA_CLINIC_ID
--                             (aparece 7 veces, en las políticas).
--   2. 'CAMBIA_ESTA_CLAVE' -> una contraseña fuerte y aleatoria.
--   3. revylia_panel_ro    -> otro nombre de rol, si lo prefieres.
--
-- DESPUÉS DE EJECUTAR, configura en el backend:
--   PANEL_DATABASE_URL=postgresql://revylia_panel_ro:<clave>@<host>:<puerto>/<db>
-- NUNCA reutilices DATABASE_URL (ese es el rol dueño, que sí escribe).
--
-- GARANTÍAS ESTRUCTURALES DE SOLO LECTURA (las cuatro, juntas):
--   a) El rol NO es dueño de ninguna tabla  -> RLS sí se le aplica.
--   b) NOBYPASSRLS                          -> no puede saltarse RLS.
--   c) Solo se otorga SELECT; INSERT/UPDATE/DELETE/TRUNCATE se revocan
--      explícitamente y no se otorgan en ningún momento.
--   d) `ALTER ROLE ... SET default_transaction_read_only = on` marca la
--      sesión como de solo lectura desde el arranque (defensa en
--      profundidad: es reversible dentro de la sesión, por eso (a)-(c)
--      son la garantía real y esto solo es una capa extra).
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Rol de login, sin privilegios especiales
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'revylia_panel_ro') THEN
        CREATE ROLE revylia_panel_ro
            LOGIN
            PASSWORD 'CAMBIA_ESTA_CLAVE'
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOREPLICATION
            NOBYPASSRLS;
    END IF;
END
$$;

-- Idempotente: reaplica los atributos aunque el rol ya existiera.
-- `NOINHERIT` y `LOGIN` se incluyen explícitamente: sin `NOINHERIT`, un rol
-- `revylia_panel_ro` preexistente que perteneciera a algún grupo privilegiado
-- conservaría los privilegios de escritura heredados y esta migración no se
-- los quitaría, aunque el bloque `DO $$` de arriba sí lo declara al crearlo.
ALTER ROLE revylia_panel_ro
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS NOREPLICATION;

-- Si el rol venía de antes, pudo quedar dentro de algún grupo. Se sale de
-- todos: la pertenencia es la vía más silenciosa de recuperar escritura.
DO $$
DECLARE grupo text;
BEGIN
    FOR grupo IN
        SELECT g.rolname
        FROM pg_auth_members m
        JOIN pg_roles g ON g.oid = m.roleid
        JOIN pg_roles r ON r.oid = m.member
        WHERE r.rolname = 'revylia_panel_ro'
    LOOP
        EXECUTE format('REVOKE %I FROM revylia_panel_ro', grupo);
        RAISE NOTICE 'revylia_panel_ro salió del grupo %', grupo;
    END LOOP;
END
$$;

-- Toda sesión de este rol arranca en solo lectura. Un `SET` del lado del
-- cliente no sobrevive de forma fiable al transaction pooler de Supabase;
-- este default lo aplica el servidor al abrir la sesión.
ALTER ROLE revylia_panel_ro SET default_transaction_read_only = on;

-- Cortafuegos contra consultas accidentalmente pesadas desde el panel.
ALTER ROLE revylia_panel_ro SET statement_timeout = '15s';
ALTER ROLE revylia_panel_ro SET idle_in_transaction_session_timeout = '30s';


-- ---------------------------------------------------------------------
-- 2. Privilegios: SELECT y nada más
-- ---------------------------------------------------------------------
GRANT USAGE ON SCHEMA revylia TO revylia_panel_ro;

GRANT SELECT ON
    revylia.clinics,
    revylia.patients,
    revylia.appointments,
    revylia.opportunities,
    revylia.escalations,
    revylia.recovery_messages,
    revylia.whatsapp_inbound_events
TO revylia_panel_ro;

-- Explícito aunque nunca se hayan otorgado: si alguien corrió un
-- `GRANT ALL` en el pasado, esto lo deshace.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA revylia FROM revylia_panel_ro;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA revylia FROM revylia_panel_ro;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA revylia FROM revylia_panel_ro;
REVOKE CREATE ON SCHEMA revylia FROM revylia_panel_ro;

-- PUBLIC: el agujero que revocar solo del rol no tapa.
--
-- PostgreSQL concede por defecto `EXECUTE` sobre TODA función a `PUBLIC`, y en
-- PG <= 14 también `CREATE` sobre el esquema `public`. Revocar únicamente de
-- `revylia_panel_ro` no quita ninguna de las dos, porque no las tiene a título
-- propio: las hereda de `PUBLIC`. Hoy no hay funciones en `revylia`, así que
-- esto es latente, pero el día que alguien añada una `SECURITY DEFINER` sería
-- una vía de escritura desde un rol "de solo lectura".
--
-- `default_transaction_read_only` NO cierra ese hueco: es revertible con un
-- `SET` desde la propia sesión.
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA revylia FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;      -- no-op en PG >= 15
REVOKE CREATE ON SCHEMA public FROM revylia_panel_ro;

-- Las tablas y funciones que se creen a futuro no llegan al panel por
-- accidente con más permisos de los debidos.
--
-- `ALTER DEFAULT PRIVILEGES` sin `FOR ROLE` solo afecta a los objetos que cree
-- EL ROL QUE EJECUTA ESTE SCRIPT. En Supabase las migraciones suelen correrlas
-- `postgres` o `supabase_admin`, así que se declaran explícitamente: sin esto,
-- una tabla futura creada por otro rol no quedaría cubierta.
DO $$
DECLARE propietario text;
BEGIN
    FOREACH propietario IN ARRAY ARRAY['postgres', 'supabase_admin', current_user]
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = propietario) THEN
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA revylia '
                'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLES FROM revylia_panel_ro',
                propietario
            );
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA revylia '
                'REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC',
                propietario
            );
        END IF;
    END LOOP;
END
$$;

-- AVISO sobre tablas futuras: el riesgo real no es que el panel tenga DEMASIADOS
-- permisos sobre una tabla nueva, sino que tenga DEMASIADO POCOS. Una tabla
-- añadida a `revylia` sin `GRANT SELECT` y sin política `FOR SELECT` devolverá
-- cero filas sin error, igual que describe la cabecera de este archivo. Al
-- añadir una tabla al esquema hay que volver a ejecutar esta migración.


-- ---------------------------------------------------------------------
-- 3. Políticas RLS — SIN ESTO EL PANEL VE CERO FILAS
-- ---------------------------------------------------------------------
-- Una política por tabla, solo `FOR SELECT`, solo para este rol, fijada a
-- la clínica configurada. En `clinics` el filtro es sobre `id` porque esa
-- tabla no tiene columna `clinic_id`.
--
-- Se usa el literal de la clínica (y NO `current_setting(...)`) a
-- propósito: `current_setting('revylia.clinic_id', true)` devuelve NULL si
-- la variable no está puesta, `clinic_id = NULL` es NULL, y el resultado
-- vuelve a ser CERO FILAS SIN ERROR — justo el fallo silencioso que este
-- archivo existe para evitar. Además, con transaction pooling el `SET` del
-- cliente puede no sobrevivir entre sentencias.
-- Al final del archivo queda la variante con `current_setting` comentada,
-- por si algún día el despliegue es multi-clínica y usa conexiones
-- dedicadas (`src/panel/db.py` ya hace el `set_config` correspondiente).

DROP POLICY IF EXISTS panel_ro_clinics ON revylia.clinics;
CREATE POLICY panel_ro_clinics ON revylia.clinics
    FOR SELECT TO revylia_panel_ro
    USING (id = 'clinica-sonrisas');

DROP POLICY IF EXISTS panel_ro_patients ON revylia.patients;
CREATE POLICY panel_ro_patients ON revylia.patients
    FOR SELECT TO revylia_panel_ro
    USING (clinic_id = 'clinica-sonrisas');

DROP POLICY IF EXISTS panel_ro_appointments ON revylia.appointments;
CREATE POLICY panel_ro_appointments ON revylia.appointments
    FOR SELECT TO revylia_panel_ro
    USING (clinic_id = 'clinica-sonrisas');

DROP POLICY IF EXISTS panel_ro_opportunities ON revylia.opportunities;
CREATE POLICY panel_ro_opportunities ON revylia.opportunities
    FOR SELECT TO revylia_panel_ro
    USING (clinic_id = 'clinica-sonrisas');

DROP POLICY IF EXISTS panel_ro_escalations ON revylia.escalations;
CREATE POLICY panel_ro_escalations ON revylia.escalations
    FOR SELECT TO revylia_panel_ro
    USING (clinic_id = 'clinica-sonrisas');

DROP POLICY IF EXISTS panel_ro_recovery_messages ON revylia.recovery_messages;
CREATE POLICY panel_ro_recovery_messages ON revylia.recovery_messages
    FOR SELECT TO revylia_panel_ro
    USING (clinic_id = 'clinica-sonrisas');

DROP POLICY IF EXISTS panel_ro_events ON revylia.whatsapp_inbound_events;
CREATE POLICY panel_ro_events ON revylia.whatsapp_inbound_events
    FOR SELECT TO revylia_panel_ro
    USING (clinic_id = 'clinica-sonrisas');


-- ---------------------------------------------------------------------
-- 4. Verificación manual (ejecuta esto después y lee los resultados)
-- ---------------------------------------------------------------------
-- 4.1 El rol NO debe ser dueño de ninguna tabla y NO debe tener BYPASSRLS.
--     Esperado: rolbypassrls = false, rolsuper = false.
--
--   SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole
--   FROM pg_roles WHERE rolname = 'revylia_panel_ro';
--
--   SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'revylia';
--   -- tableowner NUNCA debe ser revylia_panel_ro.
--
-- 4.2 Privilegios efectivos. Esperado: solo 'SELECT'.
--
--   SELECT table_name, privilege_type
--   FROM information_schema.role_table_grants
--   WHERE grantee = 'revylia_panel_ro' AND table_schema = 'revylia'
--   ORDER BY table_name, privilege_type;
--
-- 4.3 Las 7 políticas existen.
--
--   SELECT tablename, policyname, cmd, roles
--   FROM pg_policies WHERE schemaname = 'revylia' ORDER BY tablename;
--
-- 4.4 Prueba real conectándote COMO revylia_panel_ro:
--
--   SELECT count(*) FROM revylia.patients;        -- debe devolver > 0
--   INSERT INTO revylia.patients (clinic_id, name) VALUES ('x','y');
--   -- debe fallar con "permission denied for table patients"


-- ---------------------------------------------------------------------
-- 5. VARIANTE MULTI-CLÍNICA (comentada; NO la actives sin leer el aviso)
-- ---------------------------------------------------------------------
-- Si algún día hay más de una clínica y el panel usa conexiones dedicadas
-- (sin transaction pooler), se pueden reemplazar las políticas por:
--
--   CREATE POLICY panel_ro_patients ON revylia.patients
--       FOR SELECT TO revylia_panel_ro
--       USING (clinic_id = current_setting('revylia.clinic_id', true));
--
-- AVISO: si `revylia.clinic_id` no está puesta en la sesión, la condición
-- es NULL y el panel ve CERO FILAS sin ningún error. `src/panel/db.py`
-- ejecuta `set_config('revylia.clinic_id', <clinic>, false)` al abrir la
-- conexión precisamente para cubrir este caso, pero con pooling de
-- transacciones ese ajuste puede perderse entre sentencias. Por eso el
-- literal fijo es la opción por defecto de este archivo.
