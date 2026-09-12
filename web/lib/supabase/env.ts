/**
 * Lectura de variables de entorno de Supabase (§1 del contrato).
 *
 * Solo se usa la clave **anónima** (`NEXT_PUBLIC_SUPABASE_ANON_KEY`).
 * Nunca se lee ni se expone una `service_role` en el frontend.
 */

export interface SupabaseEnv {
  url: string;
  anonKey: string;
}

/**
 * Devuelve la configuración de Supabase o `null` si falta.
 *
 * Las referencias a `process.env.NEXT_PUBLIC_*` son literales a propósito:
 * Next las sustituye en tiempo de compilación y solo así llegan al navegador.
 */
export function getSupabaseEnv(): SupabaseEnv | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) return null;
  return { url, anonKey };
}

export function requireSupabaseEnv(): SupabaseEnv {
  const env = getSupabaseEnv();
  if (!env) {
    throw new Error(
      "Faltan NEXT_PUBLIC_SUPABASE_URL y/o NEXT_PUBLIC_SUPABASE_ANON_KEY. Revisa web/.env.example.",
    );
  }
  return env;
}

/**
 * Interruptor del guard de autenticación.
 *
 * Por defecto está **desactivado** para que la demo sin Supabase abra directo en
 * el panel. En cualquier despliegue con datos reales **debe** valer `"true"`.
 *
 * Solo es legible en el servidor (no lleva prefijo `NEXT_PUBLIC_`), que es donde
 * corren el middleware y los Server Components.
 */
export function isAuthEnabled(): boolean {
  return process.env.PANEL_AUTH_ENABLED === "true";
}

/** Metadato protegido que habilita el acceso (§2). NUNCA `user_metadata`. */
export const PANEL_FLAG = "revylia_panel";
