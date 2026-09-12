/**
 * Cliente de la API del panel — `docs/CONTRACT_PANEL.md` §4, §5 y §7.
 *
 * Dos modos, decididos por `PANEL_API_URL`:
 *
 * 1. **Modo demo (por defecto, sin `PANEL_API_URL`)**: no se hace ninguna
 *    petición de red. Los datos salen de `@/lib/demo/fixtures` y la envoltura
 *    de §4 es idéntica, con `meta.source = "demo:fixtures"` para que `<QueryMeta>`
 *    deje claro que son datos de demostración.
 * 2. **Modo real (con `PANEL_API_URL`)**: `fetch` contra FastAPI **desde el
 *    servidor**, adjuntando `Authorization: Bearer <access_token>` de la sesión
 *    Supabase. El backend nunca se expone al navegador.
 *
 * Reglas duras:
 * - `clinic_id` JAMÁS se envía desde el cliente (§0.2). Si llega en `params` se descarta.
 * - Nunca se registran en logs el token, las cabeceras ni los parámetros de consulta
 *   (pueden contener nombres o teléfonos de pacientes).
 * - **Vacío no es fallo (§4):** `200` con `data: []` devuelve una envoltura normal
 *   con `data` vacío → A5 pinta `<EmptyState>`. Solo un fallo real lanza
 *   `PanelApiError` (p. ej. `503 upstream_unavailable`) → A5 pinta `<ErrorState>`.
 */

import {
  DEMO_SOURCE,
  buildAvailability,
  demoAppointments,
  demoAvailability,
  demoCatalog,
  demoEscalations,
  demoEvents,
  demoOpportunities,
  demoPatients,
  demoRecovery,
  demoSummary,
} from "@/lib/demo/fixtures";
import type { ApiEnvelope, ApiErrorType, ApiMeta } from "@/lib/types";

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

/** Error normalizado de §4. `type` siempre es uno de los cinco del contrato. */
export class PanelApiError extends Error {
  readonly type: ApiErrorType;
  /** Código HTTP cuando lo hubo. `undefined` en fallos de red o de configuración. */
  readonly status?: number;

  constructor(type: ApiErrorType, message: string, status?: number) {
    super(message);
    this.name = "PanelApiError";
    this.type = type;
    this.status = status;
  }
}

export function isPanelApiError(error: unknown): error is PanelApiError {
  return error instanceof PanelApiError;
}

const ERROR_TYPES: readonly ApiErrorType[] = [
  "unauthorized",
  "forbidden",
  "not_found",
  "validation_error",
  "upstream_unavailable",
];

/** Mensajes en español por tipo, para cuando el backend no envía uno usable. */
const DEFAULT_MESSAGES: Record<ApiErrorType, string> = {
  unauthorized: "Tu sesión expiró. Vuelve a iniciar sesión.",
  forbidden: "Tu cuenta no tiene habilitado el acceso al panel.",
  not_found: "No se encontró el recurso solicitado.",
  validation_error: "Los filtros enviados no son válidos.",
  upstream_unavailable: "No se pudo consultar la información. Intenta de nuevo.",
};

function statusToType(status: number): ApiErrorType {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 400 || status === 409 || status === 422) return "validation_error";
  return "upstream_unavailable";
}

// ---------------------------------------------------------------------------
// Parámetros
// ---------------------------------------------------------------------------

export type PanelFetchParams = Record<string, string | number | boolean | null | undefined>;

/** §0.2: el cliente nunca elige la clínica. El servidor la fija desde `REVYLIA_CLINIC_ID`. */
const FORBIDDEN_PARAMS = new Set(["clinic_id", "clinicId"]);

function cleanParams(params?: PanelFetchParams): Record<string, string> {
  const clean: Record<string, string> = {};
  if (!params) return clean;
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (FORBIDDEN_PARAMS.has(key)) continue;
    clean[key] = String(value);
  }
  return clean;
}

/** `true` cuando no hay backend configurado y se sirven fixtures. */
export function isDemoMode(): boolean {
  return !process.env.PANEL_API_URL;
}

/** Normaliza `"/patients"` y `"/api/v1/patients"` a `"/patients"`. */
function normalizePath(path: string): string {
  let p = path.startsWith("/") ? path : `/${path}`;
  if (p.startsWith("/api/v1")) p = p.slice("/api/v1".length) || "/";
  if (p.length > 1 && p.endsWith("/")) p = p.slice(0, -1);
  return p;
}

// ---------------------------------------------------------------------------
// API pública
// ---------------------------------------------------------------------------

/**
 * Consulta un endpoint de §5 y devuelve la envoltura completa de §4
 * (`{ data, meta }`), porque `<QueryMeta meta />` necesita `meta`.
 *
 * @param path Ruta relativa a la API (`"/patients"`); se acepta también con el
 *             prefijo `"/api/v1"`.
 * @param params Query params de §5. `clinic_id` se ignora a propósito.
 * @throws {PanelApiError} en cualquier fallo. Una lista vacía NO es un fallo.
 */
export async function panelFetch<T>(
  path: string,
  params?: PanelFetchParams,
): Promise<ApiEnvelope<T>> {
  const endpoint = normalizePath(path);
  const query = cleanParams(params);

  if (isDemoMode()) {
    return demoFetch<T>(endpoint, query);
  }
  return realFetch<T>(endpoint, query);
}

// ---------------------------------------------------------------------------
// Modo real
// ---------------------------------------------------------------------------

const REQUEST_TIMEOUT_MS = 15_000;

async function realFetch<T>(
  endpoint: string,
  query: Record<string, string>,
): Promise<ApiEnvelope<T>> {
  if (typeof window !== "undefined") {
    // Defensa estructural: el backend del panel nunca se expone al navegador.
    throw new Error(
      "panelFetch solo puede ejecutarse en el servidor. Llámalo desde un Server Component o una Route Handler.",
    );
  }

  const base = process.env.PANEL_API_URL!.replace(/\/+$/, "");
  const search = new URLSearchParams(query).toString();
  const url = `${base}/api/v1${endpoint}${search ? `?${search}` : ""}`;

  const token = await getAccessToken();
  if (!token) {
    throw new PanelApiError("unauthorized", DEFAULT_MESSAGES.unauthorized);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: {
        // El backend verifica este JWT por su cuenta vía JWKS (§2); aquí solo se transporta.
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
      // Panel de operación: nunca servir datos cacheados.
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch {
    // No se registra la URL: los query params pueden contener datos de pacientes.
    console.error(`[panelFetch] fallo de red al consultar ${endpoint}`);
    throw new PanelApiError("upstream_unavailable", DEFAULT_MESSAGES.upstream_unavailable);
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    throw toPanelApiError(body, response.status);
  }

  const envelope = normalizeEnvelope<T>(body, endpoint);
  if (endpoint === "/catalog") {
    return { ...envelope, data: normalizeCatalog(envelope.data) as T };
  }
  return envelope;
}

/**
 * `CLINIC_KNOWLEDGE["services"]` es un diccionario `nombre → detalle` en Python.
 * La UI necesita una lista. Se acepta cualquiera de las dos formas para no
 * depender de cómo lo serialice A1.
 */
function normalizeCatalog(data: unknown): unknown {
  if (!data || typeof data !== "object") return data;
  const catalog = data as Record<string, unknown>;
  const services = catalog.services;
  if (!services || Array.isArray(services) || typeof services !== "object") return catalog;

  return {
    ...catalog,
    services: Object.entries(services as Record<string, Record<string, unknown>>).map(
      ([name, detail]) => ({ name, ...detail }),
    ),
  };
}

/**
 * Obtiene el `access_token` de la sesión Supabase del servidor.
 *
 * Se usa `getSession()` a propósito: es la única llamada que devuelve el JWT en
 * crudo. No se está autorizando con él — la autorización la hace el backend,
 * que verifica firma, `exp`, `iss` y `aud` contra el JWKS (§2), y el middleware,
 * que usa `getUser()`. Por eso no aplica la advertencia habitual sobre
 * `getSession()` en servidor.
 *
 * El import es dinámico para que el modo demo nunca arrastre `next/headers`.
 */
async function getAccessToken(): Promise<string | null> {
  try {
    const { createClient } = await import("@/lib/supabase/server");
    const supabase = await createClient();
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  } catch {
    // Nunca se registra el error tal cual: podría contener fragmentos del token.
    console.error("[panelFetch] no se pudo leer la sesión de Supabase");
    return null;
  }
}

function toPanelApiError(body: unknown, status: number): PanelApiError {
  const fallbackType = statusToType(status);
  if (body && typeof body === "object" && "error" in body) {
    const raw = (body as { error?: { type?: unknown; message?: unknown } }).error;
    const type =
      typeof raw?.type === "string" && (ERROR_TYPES as readonly string[]).includes(raw.type)
        ? (raw.type as ApiErrorType)
        : fallbackType;
    const message =
      typeof raw?.message === "string" && raw.message.trim().length > 0
        ? raw.message
        : DEFAULT_MESSAGES[type];
    return new PanelApiError(type, message, status);
  }
  return new PanelApiError(fallbackType, DEFAULT_MESSAGES[fallbackType], status);
}

/** Acepta la envoltura de §4 y completa `meta` si el backend la envía incompleta. */
function normalizeEnvelope<T>(body: unknown, endpoint: string): ApiEnvelope<T> {
  if (!body || typeof body !== "object") {
    throw new PanelApiError(
      "upstream_unavailable",
      "La respuesta del servidor no tiene el formato esperado.",
    );
  }

  const record = body as Record<string, unknown>;
  if (!("data" in record)) {
    throw new PanelApiError(
      "upstream_unavailable",
      "La respuesta del servidor no tiene el formato esperado.",
    );
  }

  const rawMeta = (record.meta ?? {}) as Partial<ApiMeta>;
  const meta: ApiMeta = {
    ...rawMeta,
    source: typeof rawMeta.source === "string" ? rawMeta.source : `revylia${endpoint}`,
    generated_at:
      typeof rawMeta.generated_at === "string" ? rawMeta.generated_at : new Date().toISOString(),
  };

  return { data: record.data as T, meta };
}

// ---------------------------------------------------------------------------
// Modo demo — mismas rutas, mismos filtros, misma envoltura
// ---------------------------------------------------------------------------

function demoMeta(extra: Partial<ApiMeta>, filters: Record<string, string>): ApiMeta {
  return {
    source: DEMO_SOURCE,
    filters,
    generated_at: new Date().toISOString(),
    ...extra,
  };
}

function paginate<T>(rows: T[], query: Record<string, string>) {
  const limit = Math.min(Math.max(Number(query.limit) || 25, 1), 100);
  const offset = Math.max(Number(query.offset) || 0, 0);
  return { rows: rows.slice(offset, offset + limit), total: rows.length, limit, offset };
}

function listEnvelope<T>(
  rows: T[],
  query: Record<string, string>,
  extra: Partial<ApiMeta> = {},
): ApiEnvelope<unknown> {
  const page = paginate(rows, query);
  return {
    data: page.rows,
    meta: demoMeta(
      {
        limit: page.limit,
        offset: page.offset,
        total: page.total,
        next_cursor: null,
        ...extra,
      },
      query,
    ),
  };
}

function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

async function demoFetch<T>(
  endpoint: string,
  query: Record<string, string>,
): Promise<ApiEnvelope<T>> {
  const envelope = resolveDemo(endpoint, query);
  return envelope as ApiEnvelope<T>;
}

function resolveDemo(endpoint: string, query: Record<string, string>): ApiEnvelope<unknown> {
  // --- /summary -----------------------------------------------------------
  if (endpoint === "/summary") {
    return { data: demoSummary, meta: demoMeta({}, query) };
  }

  // --- /catalog -----------------------------------------------------------
  if (endpoint === "/catalog") {
    return {
      data: normalizeCatalog(demoCatalog),
      meta: demoMeta({ pending_validation: true }, query),
    };
  }

  // --- /availability ------------------------------------------------------
  if (endpoint === "/availability") {
    const date = query.date;
    if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      throw new PanelApiError("validation_error", "La fecha debe tener el formato AAAA-MM-DD.");
    }
    const raw = date ? buildAvailability(date) : demoAvailability;
    // Los fixtures usan `Date.getDay()` (0 = domingo). El contrato §5.3 usa la
    // convención de Python `date.weekday()` (0 = lunes). Se normaliza aquí para
    // que demo y API real hablen el mismo idioma.
    return {
      data: { ...raw, weekday: (raw.weekday + 6) % 7 },
      meta: demoMeta({}, query),
    };
  }

  // --- /patients/{id} -----------------------------------------------------
  const patientDetail = endpoint.match(/^\/patients\/([^/]+)$/);
  if (patientDetail) {
    const id = decodeURIComponent(patientDetail[1]);
    const patient = demoPatients.find((p) => p.id === id);
    if (!patient) {
      throw new PanelApiError("not_found", "No se encontró el paciente solicitado.", 404);
    }
    return {
      data: {
        ...patient,
        appointments: demoAppointments.filter((a) => a.patient_id === id).slice(0, 20),
        opportunities: demoOpportunities.filter((o) => o.patient_id === id).slice(0, 20),
      },
      meta: demoMeta({}, query),
    };
  }

  // --- /patients ----------------------------------------------------------
  if (endpoint === "/patients") {
    let rows = [...demoPatients];
    if (query.query) {
      const needle = normalizeText(query.query);
      rows = rows.filter(
        (p) =>
          normalizeText(p.name).includes(needle) || (p.phone ?? "").includes(query.query),
      );
    }
    if (query.status) rows = rows.filter((p) => p.status === query.status);
    if (query.consent) {
      const wanted = query.consent === "true" || query.consent === "1";
      rows = rows.filter((p) => p.consent_marketing === wanted);
    }
    rows.sort((a, b) => a.name.localeCompare(b.name, "es") || Number(b.id) - Number(a.id));
    return listEnvelope(rows, query);
  }

  // --- /appointments ------------------------------------------------------
  if (endpoint === "/appointments") {
    let rows = [...demoAppointments];
    if (query.date_from) rows = rows.filter((a) => a.appointment_date >= query.date_from);
    if (query.date_to) rows = rows.filter((a) => a.appointment_date <= query.date_to);
    if (query.status) rows = rows.filter((a) => a.status === query.status);
    rows.sort(
      (a, b) =>
        b.appointment_date.localeCompare(a.appointment_date) ||
        b.appointment_time.localeCompare(a.appointment_time) ||
        Number(b.id) - Number(a.id),
    );
    return listEnvelope(rows, query);
  }

  // --- /opportunities -----------------------------------------------------
  if (endpoint === "/opportunities") {
    let rows = [...demoOpportunities];
    if (query.status) rows = rows.filter((o) => o.status === query.status);
    if (query.min_score) {
      const min = Number(query.min_score);
      if (!Number.isFinite(min)) {
        throw new PanelApiError("validation_error", "`min_score` debe ser un número.");
      }
      rows = rows.filter((o) => o.score >= min);
    }
    rows.sort(
      (a, b) =>
        b.score - a.score ||
        b.created_at.localeCompare(a.created_at) ||
        Number(b.id) - Number(a.id),
    );
    return listEnvelope(rows, query);
  }

  // --- /escalations -------------------------------------------------------
  if (endpoint === "/escalations") {
    const rank: Record<string, number> = { urgent: 0, high: 1, medium: 2, low: 3 };
    let rows = [...demoEscalations];
    if (query.status) rows = rows.filter((e) => e.status === query.status);
    if (query.priority) rows = rows.filter((e) => e.priority === query.priority);
    rows.sort(
      (a, b) =>
        rank[a.priority] - rank[b.priority] ||
        b.created_at.localeCompare(a.created_at) ||
        Number(b.id) - Number(a.id),
    );
    return listEnvelope(rows, query);
  }

  // --- /recovery ----------------------------------------------------------
  if (endpoint === "/recovery") {
    let rows = [...demoRecovery];
    if (query.status) rows = rows.filter((r) => r.status === query.status);
    rows.sort(
      (a, b) => b.created_at.localeCompare(a.created_at) || Number(b.id) - Number(a.id),
    );
    return listEnvelope(rows, query);
  }

  // --- /events ------------------------------------------------------------
  if (endpoint === "/events") {
    let rows = [...demoEvents];
    if (query.status) rows = rows.filter((e) => e.status === query.status);
    rows.sort((a, b) => b.received_at.localeCompare(a.received_at));
    // En demo no hay paginación por keyset: se devuelve la primera página.
    const limit = Math.min(Math.max(Number(query.limit) || 25, 1), 100);
    return {
      data: rows.slice(0, limit),
      meta: demoMeta({ limit, total: rows.length, next_cursor: null }, query),
    };
  }

  throw new PanelApiError("not_found", `La ruta ${endpoint} no existe en el panel.`, 404);
}
