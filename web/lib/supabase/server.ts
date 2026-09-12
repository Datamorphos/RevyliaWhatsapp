/**
 * Cliente Supabase para el servidor (Server Components, Route Handlers y
 * Server Actions), con la sesión guardada en cookies.
 *
 * **Next.js 16: `cookies()` es asíncrono** — verificado en la referencia que
 * trae el propio paquete instalado
 * (`web/node_modules/next/dist/docs/01-app/03-api-reference/04-functions/cookies.md`),
 * que documenta `const cookieStore = await cookies()`.
 *
 * Se crea un cliente nuevo en cada render: nunca se comparte entre peticiones.
 */

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import type { User } from "@supabase/supabase-js";

import { PANEL_FLAG, requireSupabaseEnv } from "./env";

export async function createClient() {
  const cookieStore = await cookies();
  const { url, anonKey } = requireSupabaseEnv();

  return createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Un Server Component no puede escribir cookies. No es un error:
          // el middleware refresca la sesión en cada petición.
        }
      },
    },
  });
}

/**
 * Usuario autenticado según el servidor de Supabase (`getUser()` valida el token
 * contra Auth, no se fía de la cookie) y si tiene el panel habilitado.
 *
 * §2: la habilitación se lee **siempre** de `app_metadata`. `user_metadata` es
 * escribible por el propio usuario y permitiría autoautorizarse.
 */
export async function getPanelUser(): Promise<{ user: User | null; enabled: boolean }> {
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    const user = data.user ?? null;
    return { user, enabled: user?.app_metadata?.[PANEL_FLAG] === true };
  } catch {
    return { user: null, enabled: false };
  }
}
