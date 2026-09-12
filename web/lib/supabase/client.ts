/**
 * Cliente Supabase para el navegador (`@supabase/ssr`).
 *
 * Se crea uno por componente de cliente; `createBrowserClient` ya reutiliza la
 * instancia internamente. Solo usa la clave anónima: cualquier dato sensible
 * queda detrás del backend, que verifica el JWT por su cuenta (§2).
 */

import { createBrowserClient } from "@supabase/ssr";

import { requireSupabaseEnv } from "./env";

export function createClient() {
  const { url, anonKey } = requireSupabaseEnv();
  return createBrowserClient(url, anonKey);
}
