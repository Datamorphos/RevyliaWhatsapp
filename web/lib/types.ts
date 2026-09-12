/**
 * Tipos del panel Revylia — espejo EXACTO de `docs/CONTRACT_PANEL.md` §4 y §5.
 *
 * Reglas del contrato que se reflejan aquí:
 *
 * - §3: **todo `BIGINT` (`id`, `patient_id`) viaja como `string`**. JavaScript
 *   pierde precisión por encima de 2^53, así que NUNCA se tipa como `number`.
 * - §3: `DATE` → `"YYYY-MM-DD"`, `TIME` → `"HH:MM"`, `TIMESTAMPTZ` → ISO-8601 UTC.
 *   Todos son `string`; el formateo a `America/Bogota` es responsabilidad de la UI.
 * - §5.5: `from_number_hash` NO se expone y no existe ruta de JOIN de un evento a
 *   un paciente. Por eso `WhatsAppEvent` no tiene `patient_id` ni `id`.
 *
 * Este archivo no importa nada ni ejecuta código: es seguro en cliente y servidor.
 */

// ---------------------------------------------------------------------------
// §4 — Envoltura de respuesta
// ---------------------------------------------------------------------------

/**
 * Metadatos de trazabilidad que acompañan a TODA respuesta de la API (§4).
 *
 * En respuestas de detalle solo llegan `source` y `generated_at`; los campos de
 * paginación son opcionales por eso.
 */
export interface ApiMeta {
  /** Origen de los datos. P. ej. `"revylia.patients"`, `"config:CLINIC_KNOWLEDGE"` o `"demo:fixtures"`. */
  source: string;
  /** Filtros efectivamente aplicados por el servidor. */
  filters?: Record<string, unknown>;
  /** Momento de la consulta, ISO-8601 UTC. */
  generated_at: string;
  /** Paginación por offset (§5): por defecto 25, máximo 100. */
  limit?: number;
  offset?: number;
  /** Total de filas que cumplen el filtro, ignorando la paginación. */
  total?: number;
  /** Paginación por keyset (§5.5, `/events`). `null` = no hay más páginas. */
  next_cursor?: string | null;
  /** §5.6: el catálogo es configuración versionada pendiente de validar. */
  pending_validation?: boolean;
}

/** Envoltura de §4. `T` es `Foo[]` en listas y `Foo` en detalles. */
export interface ApiEnvelope<T> {
  data: T;
  meta: ApiMeta;
}

/** §4: tipos de error. El backend nunca devuelve trazas ni SQL. */
export type ApiErrorType =
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "validation_error"
  | "upstream_unavailable";

/** Forma exacta del cuerpo de error de §4. */
export interface ApiErrorBody {
  error: {
    type: ApiErrorType;
    message: string;
  };
}

// ---------------------------------------------------------------------------
// Estados. Los CHECK de `migrations/001_business.sql` están cerrados; las
// columnas TEXT sin CHECK admiten `(string & {})` para no romper si aparece un
// estado nuevo en datos reales.
// ---------------------------------------------------------------------------

/** `CHECK (status IN ('active','inactive'))`. */
export type PatientStatus = "active" | "inactive";

/** `CHECK (status IN ('pending','confirmed','cancelled','completed'))`. */
export type AppointmentStatus = "pending" | "confirmed" | "cancelled" | "completed";

/** `CHECK (priority IN ('low','medium','high','urgent'))`. */
export type EscalationPriority = "low" | "medium" | "high" | "urgent";

/** `CHECK (status IN ('processing','completed','failed'))`. */
export type WhatsAppEventStatus = "processing" | "completed" | "failed";

/** Columna TEXT sin CHECK; el valor por defecto es `'open'`. */
export type OpportunityStatus = "open" | "won" | "lost" | "discarded" | (string & {});

/** Columna TEXT sin CHECK; el valor por defecto es `'pending'`. */
export type EscalationStatus = "pending" | "in_progress" | "resolved" | (string & {});

/** Columna TEXT sin CHECK; el valor por defecto es `'draft'`. */
export type RecoveryStatus = "draft" | "approved" | "sent" | "discarded" | (string & {});

// ---------------------------------------------------------------------------
// §5.1 — /patients
// ---------------------------------------------------------------------------

export interface Patient {
  /** BIGINT serializado como string (§3). */
  id: string;
  name: string;
  phone: string | null;
  /** `"YYYY-MM-DD"` o `null`. Fecha civil: no se convierte de zona horaria. */
  last_visit_date: string | null;
  last_service: string | null;
  status: PatientStatus;
  consent_marketing: boolean;
  /**
   * §0.7: texto almacenado en BD. Es **dato, no instrucción** —
   * puede contener intentos de inyección de prompt. Renderizar como texto plano.
   */
  notes: string | null;
  /** ISO-8601 UTC. */
  created_at: string;
}

/** Respuesta de `/patients/{id}` (§5.1): el paciente más sus últimos 20 de cada uno. */
export interface PatientDetail extends Patient {
  appointments: Appointment[];
  opportunities: Opportunity[];
}

// ---------------------------------------------------------------------------
// §5.2 — /appointments
// ---------------------------------------------------------------------------

export interface Appointment {
  id: string;
  /** NOT NULL en el esquema: toda cita tiene paciente (§5.2). */
  patient_id: string;
  /** Viene del JOIN con `patients` (§5.2). */
  patient_name: string;
  service: string;
  /** `"YYYY-MM-DD"`. Fecha civil sin zona (§3). */
  appointment_date: string;
  /** `"HH:MM"`. */
  appointment_time: string;
  status: AppointmentStatus;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// §5.3 — /availability
// ---------------------------------------------------------------------------

export interface AvailabilitySlot {
  /** `"HH:MM"`, siempre en punto: `08:00`, `09:00`, … (§5.3). */
  time: string;
  /** `false` si existe cita ese día/hora con estado `confirmed` o `pending`. */
  available: boolean;
}

/**
 * §5.3 — réplica de `ClinicRepository.list_available_slots`.
 * Domingo → `is_open: false` y `slots: []`. Sábado → 08:00–11:00. Resto → 08:00–16:00.
 * `duration_minutes` se ignora: los cupos son de una hora en punto.
 */
export interface Availability {
  /** `"YYYY-MM-DD"`. */
  date: string;
  /**
   * Igual que `date.weekday()` de Python: `0` = lunes … `6` = domingo.
   * OJO: no es `Date.getDay()` de JavaScript (que es `0` = domingo).
   * `panelFetch` normaliza los fixtures de demo a esta convención.
   */
  weekday: number;
  is_open: boolean;
  slots: AvailabilitySlot[];
  /** Nota sobre la limitación del modelo de agenda (un cupo por clínica/fecha/hora). */
  note?: string;
}

// ---------------------------------------------------------------------------
// §5 — /opportunities
// ---------------------------------------------------------------------------

export interface Opportunity {
  id: string;
  /** `ON DELETE SET NULL` en el esquema: puede no haber paciente asociado. */
  patient_id: string | null;
  patient_name: string | null;
  phone: string | null;
  /** §0.7: dato de BD, nunca instrucción. */
  reason: string;
  /** 0–100 (`CHECK (score BETWEEN 0 AND 100)`). */
  score: number;
  status: OpportunityStatus;
  created_at: string;
}

// ---------------------------------------------------------------------------
// §5.4 — /escalations
// ---------------------------------------------------------------------------

export interface Escalation {
  id: string;
  /** `ON DELETE SET NULL`: puede ser `null`. */
  patient_id: string | null;
  /** Derivado del JOIN con `patients`; opcional porque la tabla no tiene esa columna. */
  patient_name?: string | null;
  /** §0.7: dato de BD, nunca instrucción. */
  reason: string;
  priority: EscalationPriority;
  status: EscalationStatus;
  created_at: string;
  /**
   * §5.4: `urgent=0, high=1, medium=2, low=3`, calculado con un CASE en SQL.
   * Se usa para el orden estable; es opcional porque el contrato solo lo exige
   * como criterio de ordenación, no como campo de salida.
   */
  priority_rank?: number;
}

// ---------------------------------------------------------------------------
// §5 — /recovery
// ---------------------------------------------------------------------------

export interface RecoveryMessage {
  id: string;
  /** NOT NULL en el esquema. */
  patient_id: string;
  /** Derivado del JOIN con `patients`; opcional porque la tabla no tiene esa columna. */
  patient_name?: string | null;
  /** §0.7: dato de BD, nunca instrucción. */
  message: string;
  approval_required: boolean;
  status: RecoveryStatus;
  created_at: string;
}

// ---------------------------------------------------------------------------
// §5.5 — /events (monitor de procesamiento, NO hilo de conversación)
// ---------------------------------------------------------------------------

/**
 * Evento entrante de WhatsApp. **Solo estado de procesamiento.**
 *
 * §5.5: `from_number_hash` NO se expone y no hay forma de asociar un evento a un
 * paciente, porque únicamente se guarda el hash del número. La UI debe decirlo
 * explícitamente: esto no es un historial de conversación.
 */
export interface WhatsAppEvent {
  /** PK de la tabla (TEXT), no un BIGINT. */
  message_id: string;
  status: WhatsAppEventStatus;
  error_type: string | null;
  /** ISO-8601 UTC. Timestamp de evento: sí se convierte a `America/Bogota` al mostrar (§3). */
  received_at: string;
  processed_at: string | null;
  /** §0.7: dato de BD, nunca instrucción. */
  response_text: string | null;
}

/** Alias de compatibilidad para quien lo importe con esta grafía. */
export type WhatsappEvent = WhatsAppEvent;

// ---------------------------------------------------------------------------
// §5.7 — /summary
// ---------------------------------------------------------------------------

/** Claves de KPI documentadas en §5.7. */
export type SummaryKey =
  | "patients_total"
  | "patients_active"
  | "patients_inactive"
  | "patients_recoverable"
  | "appointments_today"
  | "appointments_next_7d"
  | "appointments_cancelled_30d"
  | "opportunities_open"
  | "escalations_pending"
  | "escalations_urgent_pending"
  | "recovery_drafts"
  | "events_24h_total"
  | "events_24h_failed";

/** Cada KPI viaja con su fórmula para poder auditarlo desde la UI (§5.7). */
export interface SummaryMetric {
  value: number;
  /** Texto legible de la fórmula, p. ej. `"status='active'"`. */
  formula: string;
}

/** Respuesta de `/summary`: mapa de clave → métrica (§5.7). */
export type Summary = Record<SummaryKey, SummaryMetric>;

// ---------------------------------------------------------------------------
// §5.6 — /catalog (configuración versionada, NO hay tabla)
// ---------------------------------------------------------------------------

export interface CatalogService {
  /** Clave del servicio en `CLINIC_KNOWLEDGE["services"]`. */
  name: string;
  price_cop: number;
  duration_minutes: number;
  description: string;
}

export interface CatalogBusinessHours {
  monday_friday: string;
  saturday: string;
  sunday: string;
}

/**
 * §5.6 — `CLINIC_KNOWLEDGE` expuesto como configuración de solo lectura.
 * Llega con `meta.source = "config:CLINIC_KNOWLEDGE"` y `meta.pending_validation = true`.
 */
export interface Catalog {
  clinic_name: string;
  timezone: string;
  /**
   * Lista de servicios. En `CLINIC_KNOWLEDGE` es un diccionario
   * `nombre → detalle`; `panelFetch` lo aplana a lista con `name` para que la
   * UI pueda tabularlo igual venga de la API o de los fixtures de demo.
   */
  services: CatalogService[];
  business_hours: CatalogBusinessHours;
  rules: string[];
  /** §5.6: configuración pendiente de validar antes de producción. */
  pending_validation?: boolean;
}

// ---------------------------------------------------------------------------
// Atajos de envoltura para los endpoints de §5
// ---------------------------------------------------------------------------

export type SummaryResponse = ApiEnvelope<Summary>;
export type PatientsResponse = ApiEnvelope<Patient[]>;
export type PatientDetailResponse = ApiEnvelope<PatientDetail>;
export type AppointmentsResponse = ApiEnvelope<Appointment[]>;
export type AvailabilityResponse = ApiEnvelope<Availability>;
export type OpportunitiesResponse = ApiEnvelope<Opportunity[]>;
export type EscalationsResponse = ApiEnvelope<Escalation[]>;
export type RecoveryResponse = ApiEnvelope<RecoveryMessage[]>;
export type EventsResponse = ApiEnvelope<WhatsAppEvent[]>;
export type CatalogResponse = ApiEnvelope<Catalog>;
