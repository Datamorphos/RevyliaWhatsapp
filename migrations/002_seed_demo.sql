INSERT INTO revylia.clinics (id, name, timezone)
VALUES ('clinica-sonrisas', 'Clínica Sonrisas S.A.S.', 'America/Bogota')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    timezone = EXCLUDED.timezone;

INSERT INTO revylia.patients
    (clinic_id, name, phone, last_visit_date, last_service, status, consent_marketing, notes)
VALUES
    ('clinica-sonrisas', 'Laura Gómez', '3001112233', CURRENT_DATE - INTERVAL '220 days', 'Limpieza dental', 'inactive', true, 'Interés previo en blanqueamiento'),
    ('clinica-sonrisas', 'Carlos Ruiz', '3012223344', CURRENT_DATE - INTERVAL '400 days', 'Valoración general', 'inactive', true, 'No respondió el último recordatorio'),
    ('clinica-sonrisas', 'Mariana López', '3023334455', CURRENT_DATE - INTERVAL '35 days', 'Ortodoncia - control', 'active', true, 'Paciente en tratamiento'),
    ('clinica-sonrisas', 'Andrés Torres', '3034445566', CURRENT_DATE - INTERVAL '190 days', 'Limpieza dental', 'inactive', false, 'No autoriza mensajes comerciales'),
    ('clinica-sonrisas', 'Sofía Martínez', '3045556677', CURRENT_DATE - INTERVAL '310 days', 'Blanqueamiento', 'inactive', true, 'Posible seguimiento semestral')
ON CONFLICT (clinic_id, phone) DO UPDATE SET
    name = EXCLUDED.name,
    last_visit_date = EXCLUDED.last_visit_date,
    last_service = EXCLUDED.last_service,
    status = EXCLUDED.status,
    consent_marketing = EXCLUDED.consent_marketing,
    notes = EXCLUDED.notes;

INSERT INTO revylia.appointments
    (clinic_id, patient_id, service, appointment_date, appointment_time, status)
SELECT
    'clinica-sonrisas', p.id, 'Ortodoncia - control', CURRENT_DATE + 1, '10:00', 'confirmed'
FROM revylia.patients p
WHERE p.clinic_id = 'clinica-sonrisas' AND p.phone = '3023334455'
ON CONFLICT DO NOTHING;
