/**
 * Formateo de presentación del panel Revylia — todo en español (es-CO).
 *
 * Regla temporal del contrato (§3 de `docs/CONTRACT_PANEL.md`):
 *
 * - Las **fechas de cita** (`appointment_date`, `last_visit_date`, …) son
 *   fechas civiles `YYYY-MM-DD` **sin zona horaria**. Se formatean tal cual,
 *   SIN convertir: usa `formatCivilDate` / `formatCivilDateShort` / `formatCivilWeekday`.
 *   Nunca pases esas cadenas a `new Date(...)` directamente: `new Date("2026-09-12")`
 *   se interpreta como medianoche UTC y en Bogotá (UTC-5) retrocede un día.
 *
 * - Los **timestamps de evento** (`received_at`, `processed_at`, `created_at`,
 *   `generated_at`, …) llegan como ISO-8601 UTC y SÍ se convierten a
 *   `America/Bogota` para mostrarse: usa `formatTimestamp` / `formatTimestampTime`.
 *
 * La conversión de zona se hace con `Intl.DateTimeFormat` porque el proyecto
 * solo tiene `date-fns` v4 (sin `@date-fns/tz`) y ningún agente instala paquetes.
 */

import { formatDistance, format as formatWithPattern } from "date-fns"
import { es } from "date-fns/locale"

/** Marcador para valores ausentes. Un guion largo se lee mejor que "null". */
export const PLACEHOLDER = "—"

/** Zona horaria de presentación de la clínica (§3). */
export const CLINIC_TIME_ZONE = "America/Bogota"

const LOCALE = "es-CO"

/* -------------------------------------------------------------------------- */
/* Fechas civiles (sin zona horaria)                                           */
/* -------------------------------------------------------------------------- */

const CIVIL_DATE = /^(\d{4})-(\d{2})-(\d{2})/

/**
 * Convierte `"YYYY-MM-DD"` en un `Date` local a medianoche, sin desplazamiento
 * de zona. Devuelve `null` si la cadena no es una fecha civil válida.
 */
export function parseCivilDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const match = CIVIL_DATE.exec(value)
  if (!match) return null
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3])
  )
  return Number.isNaN(date.getTime()) ? null : date
}

/** `"2026-09-12"` → `"12 de septiembre de 2026"`. */
export function formatCivilDate(value: string | null | undefined): string {
  const date = parseCivilDate(value)
  if (!date) return PLACEHOLDER
  return formatWithPattern(date, "d 'de' MMMM 'de' yyyy", { locale: es })
}

/** `"2026-09-12"` → `"12/09/2026"`. Para celdas de tabla densas. */
export function formatCivilDateShort(value: string | null | undefined): string {
  const date = parseCivilDate(value)
  if (!date) return PLACEHOLDER
  return formatWithPattern(date, "dd/MM/yyyy", { locale: es })
}

/** `"2026-09-12"` → `"sábado, 12 de septiembre"`. Para encabezados de agenda. */
export function formatCivilWeekday(value: string | null | undefined): string {
  const date = parseCivilDate(value)
  if (!date) return PLACEHOLDER
  return formatWithPattern(date, "EEEE, d 'de' MMMM", { locale: es })
}

/** `"2026-09-12"` → `"sáb"`. Etiqueta mínima de día. */
export function formatCivilWeekdayShort(
  value: string | null | undefined
): string {
  const date = parseCivilDate(value)
  if (!date) return PLACEHOLDER
  return formatWithPattern(date, "EEE", { locale: es })
}

/** Fecha civil de hoy en la zona de la clínica, como `"YYYY-MM-DD"`. */
export function todayCivilDate(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: CLINIC_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date())
  return parts
}

/* -------------------------------------------------------------------------- */
/* Horas de cita (`HH:MM`, también sin zona)                                   */
/* -------------------------------------------------------------------------- */

/** `"08:00:00"` o `"8:00"` → `"08:00"`. Formato 24 h, sin conversión. */
export function formatTime(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER
  const match = /^(\d{1,2}):(\d{2})/.exec(value)
  if (!match) return value
  return `${match[1].padStart(2, "0")}:${match[2]}`
}

/** `"2026-09-12"` + `"08:00"` → `"12/09/2026 08:00"`. */
export function formatCivilDateTime(
  date: string | null | undefined,
  time: string | null | undefined
): string {
  const day = formatCivilDateShort(date)
  const hour = formatTime(time)
  if (day === PLACEHOLDER) return hour
  if (hour === PLACEHOLDER) return day
  return `${day} ${hour}`
}

/* -------------------------------------------------------------------------- */
/* Timestamps (ISO-8601 UTC → America/Bogota)                                  */
/* -------------------------------------------------------------------------- */

function parseTimestamp(value: string | Date | null | undefined): Date | null {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const timestampFormat = new Intl.DateTimeFormat(LOCALE, {
  timeZone: CLINIC_TIME_ZONE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
})

const timestampTimeFormat = new Intl.DateTimeFormat(LOCALE, {
  timeZone: CLINIC_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
})

const timestampDateFormat = new Intl.DateTimeFormat(LOCALE, {
  timeZone: CLINIC_TIME_ZONE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
})

const timestampLongFormat = new Intl.DateTimeFormat(LOCALE, {
  timeZone: CLINIC_TIME_ZONE,
  dateStyle: "long",
  timeStyle: "short",
  hour12: false,
})

/** ISO UTC → `"12/09/2026, 15:04"` en hora de Bogotá. */
export function formatTimestamp(value: string | Date | null | undefined): string {
  const date = parseTimestamp(value)
  return date ? timestampFormat.format(date) : PLACEHOLDER
}

/** ISO UTC → `"15:04"` en hora de Bogotá. */
export function formatTimestampTime(
  value: string | Date | null | undefined
): string {
  const date = parseTimestamp(value)
  return date ? timestampTimeFormat.format(date) : PLACEHOLDER
}

/** ISO UTC → `"12/09/2026"` en hora de Bogotá. */
export function formatTimestampDate(
  value: string | Date | null | undefined
): string {
  const date = parseTimestamp(value)
  return date ? timestampDateFormat.format(date) : PLACEHOLDER
}

/** ISO UTC → `"12 de septiembre de 2026, 15:04"` en hora de Bogotá. */
export function formatTimestampLong(
  value: string | Date | null | undefined
): string {
  const date = parseTimestamp(value)
  return date ? timestampLongFormat.format(date) : PLACEHOLDER
}

/**
 * ISO UTC → `"hace 5 minutos"` / `"en 2 horas"`.
 *
 * El resultado depende del reloj, así que **solo debe usarse en componentes de
 * cliente después del montaje** (o pasando `now` explícitamente, que es lo que
 * lo vuelve determinista y testeable). Renderizarlo en el servidor y
 * rehidratarlo produce un desajuste de hidratación.
 */
export function formatRelative(
  value: string | Date | null | undefined,
  now?: Date
): string {
  const date = parseTimestamp(value)
  if (!date) return PLACEHOLDER
  return formatDistance(date, now ?? new Date(), {
    locale: es,
    addSuffix: true,
  })
}

/** Atributo `dateTime` de `<time>`: ISO-8601 normalizado o `undefined`. */
export function toISOAttribute(
  value: string | Date | null | undefined
): string | undefined {
  const date = parseTimestamp(value)
  return date ? date.toISOString() : undefined
}

/* -------------------------------------------------------------------------- */
/* Números, moneda y teléfonos                                                 */
/* -------------------------------------------------------------------------- */

const numberFormat = new Intl.NumberFormat(LOCALE)

const currencyFormat = new Intl.NumberFormat(LOCALE, {
  style: "currency",
  currency: "COP",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
})

function toNumber(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null
  const parsed = typeof value === "number" ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

/** `1234` → `"1.234"`. */
export function formatNumber(value: number | string | null | undefined): string {
  const parsed = toNumber(value)
  return parsed === null ? PLACEHOLDER : numberFormat.format(parsed)
}

/** `150000` → `"$ 150.000"` (pesos colombianos, sin decimales). */
export function formatCurrencyCOP(
  value: number | string | null | undefined
): string {
  const parsed = toNumber(value)
  return parsed === null ? PLACEHOLDER : currencyFormat.format(parsed)
}

/** `0..100` → `"72 %"`. Puntuación de oportunidad, no porcentaje real. */
export function formatScore(value: number | string | null | undefined): string {
  const parsed = toNumber(value)
  return parsed === null ? PLACEHOLDER : `${Math.round(parsed)}`
}

/**
 * Teléfonos colombianos guardados solo con dígitos (`normalize_phone`).
 * `"3001112233"` → `"+57 300 111 2233"`; `"573001112233"` → igual.
 * Si no reconoce el patrón devuelve el valor original.
 */
export function formatPhone(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER
  const digits = value.replace(/\D/g, "")
  if (!digits) return PLACEHOLDER
  const local =
    digits.length === 12 && digits.startsWith("57") ? digits.slice(2) : digits
  if (local.length === 10) {
    return `+57 ${local.slice(0, 3)} ${local.slice(3, 6)} ${local.slice(6)}`
  }
  if (local.length === 7) {
    return `${local.slice(0, 3)} ${local.slice(3)}`
  }
  return value
}

/** Devuelve el texto o el marcador si está vacío. Útil para `notes`, `reason`. */
export function orPlaceholder(value: string | null | undefined): string {
  const text = value?.trim()
  return text ? text : PLACEHOLDER
}

/** Recorta textos largos de BD para celdas de tabla. */
export function truncate(value: string | null | undefined, max = 80): string {
  const text = value?.trim()
  if (!text) return PLACEHOLDER
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

/** `true` → `"Sí"`, `false` → `"No"`. */
export function formatBoolean(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return PLACEHOLDER
  return value ? "Sí" : "No"
}

/**
 * Etiqueta legible de un filtro de `meta.filters`.
 * `{ status: "active" }` → `"status: active"`, con `null`/`undefined` omitidos
 * por el llamador (ver `QueryMeta`).
 */
export function formatFilterValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return PLACEHOLDER
  if (typeof value === "boolean") return formatBoolean(value)
  if (typeof value === "number") return formatNumber(value)
  if (Array.isArray(value)) return value.map(formatFilterValue).join(", ")
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}
