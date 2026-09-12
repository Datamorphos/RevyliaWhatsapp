/**
 * Datos de DEMOSTRACIÓN para el panel Revylia.
 *
 * Origen: `migrations/002_seed_demo.sql` (clínica y pacientes reales del seed),
 * ampliado con filas adicionales coherentes para que las tablas se vean pobladas.
 *
 * IMPORTANTE:
 * - Estos datos NO representan la configuración real de la clínica.
 * - Los KPIs de `demoSummary` se CALCULAN a partir de las filas de abajo, no se
 *   escriben a mano: así las cifras del panel siempre cuadran con las tablas
 *   (criterio de aceptación del plan).
 * - Sin dependencias: este módulo no importa nada, para que compile aunque el
 *   resto de la app aún esté a medias.
 */

// ---------------------------------------------------------------------------
// Tipos mínimos (espejo de §5 del contrato). Los ids son `string` a propósito:
// son BIGINT en PostgreSQL y JavaScript pierde precisión sobre 2^53.
// ---------------------------------------------------------------------------

export type PatientStatus = "active" | "inactive";
export type AppointmentStatus = "pending" | "confirmed" | "cancelled" | "completed";
export type Priority = "low" | "medium" | "high" | "urgent";
export type EventStatus = "processing" | "completed" | "failed";

export interface DemoPatient {
  id: string;
  name: string;
  phone: string | null;
  last_visit_date: string | null;
  last_service: string | null;
  status: PatientStatus;
  consent_marketing: boolean;
  notes: string | null;
  created_at: string;
}

export interface DemoAppointment {
  id: string;
  patient_id: string;
  patient_name: string;
  service: string;
  appointment_date: string;
  appointment_time: string;
  status: AppointmentStatus;
  created_at: string;
  updated_at: string;
}

export interface DemoOpportunity {
  id: string;
  patient_id: string | null;
  patient_name: string | null;
  phone: string | null;
  reason: string;
  score: number;
  status: string;
  created_at: string;
}

export interface DemoEscalation {
  id: string;
  patient_id: string | null;
  patient_name: string | null;
  reason: string;
  priority: Priority;
  status: string;
  created_at: string;
}

export interface DemoRecoveryMessage {
  id: string;
  patient_id: string;
  patient_name: string;
  message: string;
  approval_required: boolean;
  status: string;
  created_at: string;
}

export interface DemoEvent {
  message_id: string;
  status: EventStatus;
  error_type: string | null;
  received_at: string;
  processed_at: string | null;
  response_text: string | null;
}

// ---------------------------------------------------------------------------
// Utilidades de fecha. Todo relativo a hoy para que la demo nunca se vea vieja.
// ---------------------------------------------------------------------------

const NOW = new Date();

/** Fecha civil YYYY-MM-DD desplazada N días. Sin conversión de zona. */
function day(offset: number): string {
  const d = new Date(NOW);
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

/** Timestamp ISO desplazado N horas. */
function hoursAgo(n: number): string {
  const d = new Date(NOW.getTime() - n * 3600_000);
  return d.toISOString();
}

function daysAgoTs(n: number): string {
  const d = new Date(NOW.getTime() - n * 86_400_000);
  return d.toISOString();
}

export const TODAY = day(0);

// ---------------------------------------------------------------------------
// Pacientes — los 5 del seed + 7 adicionales
// ---------------------------------------------------------------------------

export const demoPatients: DemoPatient[] = [
  {
    id: "1", name: "Laura Gómez", phone: "3001112233",
    last_visit_date: day(-220), last_service: "Limpieza dental",
    status: "inactive", consent_marketing: true,
    notes: "Interés previo en blanqueamiento", created_at: daysAgoTs(400),
  },
  {
    id: "2", name: "Carlos Ruiz", phone: "3012223344",
    last_visit_date: day(-400), last_service: "Valoración general",
    status: "inactive", consent_marketing: true,
    notes: "No respondió el último recordatorio", created_at: daysAgoTs(430),
  },
  {
    id: "3", name: "Mariana López", phone: "3023334455",
    last_visit_date: day(-35), last_service: "Ortodoncia - control",
    status: "active", consent_marketing: true,
    notes: "Paciente en tratamiento", created_at: daysAgoTs(300),
  },
  {
    id: "4", name: "Andrés Torres", phone: "3034445566",
    last_visit_date: day(-190), last_service: "Limpieza dental",
    status: "inactive", consent_marketing: false,
    notes: "No autoriza mensajes comerciales", created_at: daysAgoTs(320),
  },
  {
    id: "5", name: "Sofía Martínez", phone: "3045556677",
    last_visit_date: day(-310), last_service: "Blanqueamiento",
    status: "inactive", consent_marketing: true,
    notes: "Posible seguimiento semestral", created_at: daysAgoTs(360),
  },
  {
    id: "6", name: "Juan Pablo Restrepo", phone: "3056667788",
    last_visit_date: day(-12), last_service: "Valoración general",
    status: "active", consent_marketing: true,
    notes: null, created_at: daysAgoTs(90),
  },
  {
    id: "7", name: "Valentina Ríos", phone: "3067778899",
    last_visit_date: day(-3), last_service: "Limpieza dental",
    status: "active", consent_marketing: true,
    notes: "Solicita cita en horario de la tarde", created_at: daysAgoTs(60),
  },
  // Homónimo deliberado: el panel debe distinguirlos por teléfono y última visita.
  {
    id: "8", name: "Carlos Ruiz", phone: "3078889900",
    last_visit_date: day(-45), last_service: "Ortodoncia - valoración",
    status: "active", consent_marketing: false,
    notes: "Homónimo de otro paciente registrado", created_at: daysAgoTs(70),
  },
  {
    id: "9", name: "Daniela Ospina", phone: "3089990011",
    last_visit_date: day(-250), last_service: "Blanqueamiento",
    status: "inactive", consent_marketing: true,
    notes: null, created_at: daysAgoTs(280),
  },
  {
    id: "10", name: "Felipe Cárdenas", phone: "3090001122",
    last_visit_date: day(-7), last_service: "Ortodoncia - control",
    status: "active", consent_marketing: true,
    notes: "Control mensual de brackets", created_at: daysAgoTs(150),
  },
  {
    id: "11", name: "Isabella Mejía", phone: "3101112244",
    last_visit_date: null, last_service: null,
    status: "active", consent_marketing: true,
    notes: "Paciente nueva, aún sin visita registrada", created_at: daysAgoTs(4),
  },
  {
    id: "12", name: "Ricardo Peña", phone: "3112223355",
    last_visit_date: day(-520), last_service: "Limpieza dental",
    status: "inactive", consent_marketing: true,
    notes: "Sin contacto hace más de un año", created_at: daysAgoTs(560),
  },
];

const patientName = (id: string) =>
  demoPatients.find((p) => p.id === id)?.name ?? "Paciente sin nombre";

// ---------------------------------------------------------------------------
// Citas
// ---------------------------------------------------------------------------

const rawAppointments: Array<Omit<DemoAppointment, "patient_name">> = [
  { id: "101", patient_id: "3", service: "Ortodoncia - control", appointment_date: day(0), appointment_time: "10:00", status: "confirmed", created_at: daysAgoTs(5), updated_at: daysAgoTs(5) },
  { id: "102", patient_id: "7", service: "Limpieza dental", appointment_date: day(0), appointment_time: "14:00", status: "confirmed", created_at: daysAgoTs(3), updated_at: daysAgoTs(3) },
  { id: "103", patient_id: "10", service: "Ortodoncia - control", appointment_date: day(0), appointment_time: "16:00", status: "pending", created_at: daysAgoTs(1), updated_at: daysAgoTs(1) },
  { id: "104", patient_id: "6", service: "Valoración general", appointment_date: day(1), appointment_time: "09:00", status: "confirmed", created_at: daysAgoTs(2), updated_at: daysAgoTs(2) },
  { id: "105", patient_id: "11", service: "Valoración general", appointment_date: day(2), appointment_time: "11:00", status: "confirmed", created_at: daysAgoTs(1), updated_at: daysAgoTs(1) },
  { id: "106", patient_id: "8", service: "Ortodoncia - valoración", appointment_date: day(3), appointment_time: "08:00", status: "pending", created_at: hoursAgo(20), updated_at: hoursAgo(20) },
  { id: "107", patient_id: "7", service: "Blanqueamiento", appointment_date: day(5), appointment_time: "15:00", status: "confirmed", created_at: hoursAgo(30), updated_at: hoursAgo(30) },
  { id: "108", patient_id: "3", service: "Ortodoncia - control", appointment_date: day(-7), appointment_time: "10:00", status: "completed", created_at: daysAgoTs(20), updated_at: daysAgoTs(7) },
  { id: "109", patient_id: "6", service: "Limpieza dental", appointment_date: day(-12), appointment_time: "09:00", status: "completed", created_at: daysAgoTs(25), updated_at: daysAgoTs(12) },
  { id: "110", patient_id: "10", service: "Ortodoncia - control", appointment_date: day(-9), appointment_time: "16:00", status: "cancelled", created_at: daysAgoTs(18), updated_at: daysAgoTs(10) },
  { id: "111", patient_id: "4", service: "Limpieza dental", appointment_date: day(-20), appointment_time: "11:00", status: "cancelled", created_at: daysAgoTs(30), updated_at: daysAgoTs(21) },
  { id: "112", patient_id: "7", service: "Limpieza dental", appointment_date: day(-3), appointment_time: "14:00", status: "completed", created_at: daysAgoTs(14), updated_at: daysAgoTs(3) },
];

export const demoAppointments: DemoAppointment[] = rawAppointments
  .map((a) => ({ ...a, patient_name: patientName(a.patient_id) }))
  .sort((a, b) =>
    b.appointment_date.localeCompare(a.appointment_date) ||
    b.appointment_time.localeCompare(a.appointment_time) ||
    Number(b.id) - Number(a.id),
  );

// ---------------------------------------------------------------------------
// Disponibilidad — réplica EXACTA de ClinicRepository.list_available_slots
// Domingo cerrado; sábado 08:00-11:00; resto 08:00-16:00. Franjas de 1 hora.
// `duration_minutes` se IGNORA a propósito: el esquema no modela duración.
// ---------------------------------------------------------------------------

export function buildAvailability(dateIso: string) {
  const weekday = new Date(`${dateIso}T12:00:00`).getDay(); // 0=domingo
  const isSunday = weekday === 0;
  const isSaturday = weekday === 6;
  const endHour = isSaturday ? 12 : 17;

  const booked = new Set(
    demoAppointments
      .filter(
        (a) =>
          a.appointment_date === dateIso &&
          (a.status === "confirmed" || a.status === "pending"),
      )
      .map((a) => a.appointment_time),
  );

  const slots = isSunday
    ? []
    : Array.from({ length: endHour - 8 }, (_, i) => {
        const time = `${String(8 + i).padStart(2, "0")}:00`;
        return { time, available: !booked.has(time) };
      });

  return {
    date: dateIso,
    weekday,
    is_open: !isSunday,
    slots,
    // Limitación verificada del esquema: un único cupo por clínica/fecha/hora.
    note: "Franjas de 1 hora y un único cupo por clínica, fecha y hora. El esquema no modela profesionales, consultorios ni duración del servicio.",
  };
}

export const demoAvailability = buildAvailability(TODAY);

// ---------------------------------------------------------------------------
// Oportunidades — incluye casos SIN paciente asociado (patient_id es nullable)
// ---------------------------------------------------------------------------

export const demoOpportunities: DemoOpportunity[] = [
  { id: "201", patient_id: "1", patient_name: "Laura Gómez", phone: "3001112233", reason: "Preguntó por blanqueamiento tras limpieza", score: 85, status: "open", created_at: hoursAgo(6) },
  { id: "202", patient_id: null, patient_name: "Contacto sin registrar", phone: "3123334455", reason: "Solicita cotización de ortodoncia por WhatsApp", score: 78, status: "open", created_at: hoursAgo(14) },
  { id: "203", patient_id: "9", patient_name: "Daniela Ospina", phone: "3089990011", reason: "Interés en retoque de blanqueamiento", score: 72, status: "open", created_at: daysAgoTs(2) },
  { id: "204", patient_id: null, patient_name: null, phone: "3134445566", reason: "Consulta de precios sin dar nombre", score: 55, status: "open", created_at: daysAgoTs(3) },
  { id: "205", patient_id: "5", patient_name: "Sofía Martínez", phone: "3045556677", reason: "Pidió información de financiación", score: 64, status: "open", created_at: daysAgoTs(4) },
  { id: "206", patient_id: "12", patient_name: "Ricardo Peña", phone: "3112223355", reason: "Respondió campaña de reactivación", score: 48, status: "closed", created_at: daysAgoTs(9) },
];

// ---------------------------------------------------------------------------
// Escalaciones
// ---------------------------------------------------------------------------

export const demoEscalations: DemoEscalation[] = [
  { id: "301", patient_id: "7", patient_name: "Valentina Ríos", reason: "Reporta dolor intenso y sangrado tras procedimiento", priority: "urgent", status: "pending", created_at: hoursAgo(2) },
  { id: "302", patient_id: null, patient_name: null, reason: "Solicita hablar con una persona, no con el asistente", priority: "high", status: "pending", created_at: hoursAgo(5) },
  { id: "303", patient_id: "4", patient_name: "Andrés Torres", reason: "Queja por cobro no reconocido", priority: "high", status: "pending", created_at: hoursAgo(26) },
  { id: "304", patient_id: "10", patient_name: "Felipe Cárdenas", reason: "Molestia con bracket suelto", priority: "medium", status: "pending", created_at: daysAgoTs(2) },
  { id: "305", patient_id: "3", patient_name: "Mariana López", reason: "Consulta administrativa sobre certificado", priority: "low", status: "resolved", created_at: daysAgoTs(6) },
];

// ---------------------------------------------------------------------------
// Mensajes de recuperación — el panel NO envía nada, solo los muestra
// ---------------------------------------------------------------------------

export const demoRecovery: DemoRecoveryMessage[] = [
  { id: "401", patient_id: "1", patient_name: "Laura Gómez", message: "Hola Laura, han pasado varios meses desde tu última limpieza dental. ¿Te gustaría agendar una valoración?", approval_required: true, status: "draft", created_at: hoursAgo(8) },
  { id: "402", patient_id: "2", patient_name: "Carlos Ruiz", message: "Hola Carlos, queremos retomar tu plan de atención. ¿Te agendamos una valoración general?", approval_required: true, status: "draft", created_at: daysAgoTs(1) },
  { id: "403", patient_id: "5", patient_name: "Sofía Martínez", message: "Hola Sofía, tu blanqueamiento fue hace un tiempo. Podemos revisar cómo va el resultado.", approval_required: true, status: "draft", created_at: daysAgoTs(2) },
  { id: "404", patient_id: "9", patient_name: "Daniela Ospina", message: "Hola Daniela, te compartimos las opciones de seguimiento disponibles este mes.", approval_required: false, status: "approved", created_at: daysAgoTs(5) },
  { id: "405", patient_id: "12", patient_name: "Ricardo Peña", message: "Hola Ricardo, nos gustaría saber cómo sigues y ofrecerte una cita de control.", approval_required: false, status: "sent", created_at: daysAgoTs(11) },
];

// ---------------------------------------------------------------------------
// Eventos de WhatsApp
//
// LIMITACIÓN VERIFICADA: la tabla solo guarda `from_number_hash`. NO existe ruta
// de JOIN a pacientes ni historial de conversación. Esto es estado de
// procesamiento, no un hilo de mensajes. `from_number_hash` no se expone.
// ---------------------------------------------------------------------------

export const demoEvents: DemoEvent[] = [
  { message_id: "wamid.HBgMNTczMDAxMTEyMjMz001", status: "completed", error_type: null, received_at: hoursAgo(1), processed_at: hoursAgo(1), response_text: "Con gusto. La limpieza dental tiene un valor de $140.000 COP y dura cerca de 60 minutos." },
  { message_id: "wamid.HBgMNTczMDIzMzM0NDU1002", status: "completed", error_type: null, received_at: hoursAgo(3), processed_at: hoursAgo(3), response_text: "Tu cita quedó confirmada para mañana a las 09:00." },
  { message_id: "wamid.HBgMNTczMTIzMzM0NDU1003", status: "failed", error_type: "LLMTimeout", received_at: hoursAgo(4), processed_at: hoursAgo(4), response_text: null },
  { message_id: "wamid.HBgMNTczMDQ1NTU2Njc3004", status: "completed", error_type: null, received_at: hoursAgo(7), processed_at: hoursAgo(7), response_text: "Te comparto los horarios disponibles para esta semana." },
  { message_id: "wamid.HBgMNTczMDY3Nzc4ODk5005", status: "processing", error_type: null, received_at: hoursAgo(0.2), processed_at: null, response_text: null },
  { message_id: "wamid.HBgMNTczMDkwMDAxMTIy006", status: "completed", error_type: null, received_at: hoursAgo(11), processed_at: hoursAgo(11), response_text: "Registré tu solicitud y un miembro del equipo te contactará." },
  { message_id: "wamid.HBgMNTczMTM0NDQ1NTY2007", status: "failed", error_type: "DatabaseUnavailable", received_at: hoursAgo(19), processed_at: hoursAgo(19), response_text: null },
  { message_id: "wamid.HBgMNTczMDM0NDQ1NTY2008", status: "completed", error_type: null, received_at: hoursAgo(23), processed_at: hoursAgo(23), response_text: "La valoración general tiene un valor de $80.000 COP." },
  { message_id: "wamid.HBgMNTczMTEyMjIzMzU1009", status: "completed", error_type: null, received_at: hoursAgo(29), processed_at: hoursAgo(29), response_text: "Gracias por escribirnos. ¿En qué te podemos ayudar?" },
  { message_id: "wamid.HBgMNTczMDU2NjY3Nzg4010", status: "completed", error_type: null, received_at: hoursAgo(36), processed_at: hoursAgo(36), response_text: "Te confirmo que la cita quedó reprogramada." },
];

// ---------------------------------------------------------------------------
// Catálogo informativo — origen: src/domain/knowledge.py (CLINIC_KNOWLEDGE).
// No existe tabla de catálogo. Configuración versionada, pendiente de validar.
// ---------------------------------------------------------------------------

export const demoCatalog = {
  clinic_name: "Clínica Sonrisas S.A.S.",
  timezone: "America/Bogota",
  services: [
    { name: "Valoración general", price_cop: 80000, duration_minutes: 45, description: "Evaluación inicial y definición del plan de atención." },
    { name: "Limpieza dental", price_cop: 140000, duration_minutes: 60, description: "Profilaxis y remoción de placa y cálculo según valoración." },
    { name: "Blanqueamiento", price_cop: 520000, duration_minutes: 90, description: "Tratamiento estético sujeto a valoración previa." },
    { name: "Ortodoncia - valoración", price_cop: 100000, duration_minutes: 60, description: "Valoración para determinar alternativas de ortodoncia." },
  ],
  business_hours: {
    monday_friday: "08:00-17:00",
    saturday: "08:00-12:00",
    sunday: "closed",
  },
  rules: [
    "Las citas deben confirmarse con nombre, teléfono, servicio, fecha y hora.",
    "Los precios son informativos y pueden cambiar después de una valoración.",
    "La cancelación o reprogramación debe solicitarse con al menos 4 horas de anticipación.",
    "No se deben emitir diagnósticos clínicos por chat.",
    "Síntomas graves, sangrado abundante, dificultad para respirar o reacciones alérgicas deben escalarse de inmediato.",
    "Solo pueden enviarse campañas a pacientes con consentimiento de comunicaciones.",
  ],
  pending_validation: true,
};

// ---------------------------------------------------------------------------
// Resumen operativo — CALCULADO a partir de las filas de arriba.
// Nunca escrito a mano: así las cifras del panel siempre cuadran con las tablas.
// ---------------------------------------------------------------------------

const RECOVERABLE_DAYS = 180;
const cutoffRecoverable = day(-RECOVERABLE_DAYS);
const in7Days = day(7);
const cutoff30 = day(-30);

function kpi(value: number, formula: string) {
  return { value, formula };
}

const activeStatuses: AppointmentStatus[] = ["confirmed", "pending"];

export const demoSummary = {
  patients_total: kpi(demoPatients.length, "COUNT(patients) de la clínica"),
  patients_active: kpi(
    demoPatients.filter((p) => p.status === "active").length,
    "patients.status = 'active'",
  ),
  patients_inactive: kpi(
    demoPatients.filter((p) => p.status === "inactive").length,
    "patients.status = 'inactive'",
  ),
  patients_recoverable: kpi(
    demoPatients.filter(
      (p) =>
        p.consent_marketing &&
        p.status === "inactive" &&
        p.last_visit_date !== null &&
        p.last_visit_date <= cutoffRecoverable,
    ).length,
    "consent_marketing AND status='inactive' AND last_visit_date <= hoy-180d",
  ),
  appointments_today: kpi(
    demoAppointments.filter(
      (a) => a.appointment_date === TODAY && activeStatuses.includes(a.status),
    ).length,
    "appointment_date = hoy AND status IN ('confirmed','pending')",
  ),
  appointments_next_7d: kpi(
    demoAppointments.filter(
      (a) =>
        a.appointment_date >= TODAY &&
        a.appointment_date <= in7Days &&
        activeStatuses.includes(a.status),
    ).length,
    "appointment_date entre hoy y hoy+7 AND status IN ('confirmed','pending')",
  ),
  appointments_cancelled_30d: kpi(
    demoAppointments.filter(
      (a) => a.status === "cancelled" && a.appointment_date >= cutoff30,
    ).length,
    "status='cancelled' AND appointment_date >= hoy-30d",
  ),
  opportunities_open: kpi(
    demoOpportunities.filter((o) => o.status === "open").length,
    "opportunities.status = 'open'",
  ),
  escalations_pending: kpi(
    demoEscalations.filter((e) => e.status === "pending").length,
    "escalations.status = 'pending'",
  ),
  escalations_urgent_pending: kpi(
    demoEscalations.filter((e) => e.status === "pending" && e.priority === "urgent").length,
    "status='pending' AND priority='urgent'",
  ),
  recovery_drafts: kpi(
    demoRecovery.filter((r) => r.status === "draft").length,
    "recovery_messages.status = 'draft'",
  ),
  events_24h_total: kpi(
    demoEvents.filter((e) => e.received_at >= hoursAgo(24)).length,
    "received_at >= now()-24h",
  ),
  events_24h_failed: kpi(
    demoEvents.filter((e) => e.received_at >= hoursAgo(24) && e.status === "failed").length,
    "received_at >= now()-24h AND status='failed'",
  ),
};

/** Marca que estos datos son de demostración, para `<QueryMeta>`. */
export const DEMO_SOURCE = "demo:fixtures";
