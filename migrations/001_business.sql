CREATE SCHEMA IF NOT EXISTS revylia;

CREATE TABLE IF NOT EXISTS revylia.clinics (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'America/Bogota',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS revylia.patients (
    id BIGSERIAL PRIMARY KEY,
    clinic_id TEXT NOT NULL REFERENCES revylia.clinics(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    phone TEXT,
    last_visit_date DATE,
    last_service TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    consent_marketing BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (clinic_id, phone)
);

CREATE TABLE IF NOT EXISTS revylia.appointments (
    id BIGSERIAL PRIMARY KEY,
    clinic_id TEXT NOT NULL REFERENCES revylia.clinics(id) ON DELETE CASCADE,
    patient_id BIGINT NOT NULL REFERENCES revylia.patients(id) ON DELETE RESTRICT,
    service TEXT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_revylia_appointment_slot
ON revylia.appointments(clinic_id, appointment_date, appointment_time)
WHERE status IN ('confirmed', 'pending');

CREATE TABLE IF NOT EXISTS revylia.opportunities (
    id BIGSERIAL PRIMARY KEY,
    clinic_id TEXT NOT NULL REFERENCES revylia.clinics(id) ON DELETE CASCADE,
    patient_id BIGINT REFERENCES revylia.patients(id) ON DELETE SET NULL,
    patient_name TEXT,
    phone TEXT,
    reason TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 50 CHECK (score BETWEEN 0 AND 100),
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS revylia.escalations (
    id BIGSERIAL PRIMARY KEY,
    clinic_id TEXT NOT NULL REFERENCES revylia.clinics(id) ON DELETE CASCADE,
    patient_id BIGINT REFERENCES revylia.patients(id) ON DELETE SET NULL,
    reason TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS revylia.recovery_messages (
    id BIGSERIAL PRIMARY KEY,
    clinic_id TEXT NOT NULL REFERENCES revylia.clinics(id) ON DELETE CASCADE,
    patient_id BIGINT NOT NULL REFERENCES revylia.patients(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    approval_required BOOLEAN NOT NULL DEFAULT true,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS revylia.whatsapp_inbound_events (
    id BIGSERIAL UNIQUE NOT NULL,
    message_id TEXT PRIMARY KEY,
    clinic_id TEXT NOT NULL REFERENCES revylia.clinics(id) ON DELETE CASCADE,
    from_number_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'failed')),
    response_text TEXT,
    error_type TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_revylia_patients_clinic_status
ON revylia.patients(clinic_id, status);

CREATE INDEX IF NOT EXISTS idx_revylia_appointments_clinic_date
ON revylia.appointments(clinic_id, appointment_date);

CREATE INDEX IF NOT EXISTS idx_revylia_events_clinic_received
ON revylia.whatsapp_inbound_events(clinic_id, received_at DESC);

-- Evita exposición accidental por Data API. El backend conectado directamente
-- a PostgreSQL con el rol de servidor sigue pudiendo operar.
ALTER TABLE revylia.clinics ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.escalations ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.recovery_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE revylia.whatsapp_inbound_events ENABLE ROW LEVEL SECURITY;
