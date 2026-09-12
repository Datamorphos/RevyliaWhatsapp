/**
 * Guard de acceso al panel (§2 del contrato).
 *
 * Protege TODO salvo `/login`, `/sin-acceso`, los callbacks de auth y los
 * assets estáticos. La lógica vive en `lib/supabase/middleware.ts`:
 *
 *  1. Sin sesión            → `/login?motivo=sesion_requerida&next=…`
 *  2. Sesión sin habilitar  → `/sin-acceso`  (`app_metadata.revylia_panel !== true`)
 *  3. Sesión habilitada     → nunca se queda en `/login` ni en `/sin-acceso`
 *
 * **Desactivado por defecto**: solo actúa si `PANEL_AUTH_ENABLED === "true"`.
 * Así la demo sin Supabase abre directamente en el panel. Actívalo en cualquier
 * entorno con datos reales.
 *
 * NOTA PARA EL ORQUESTADOR — Next.js 16 renombró `middleware` a `proxy`
 * (`middleware.ts` sigue funcionando, marcado como deprecado; el `edge runtime`
 * solo existe en `middleware`). El contrato §8 fija `web/middleware.ts`, así que
 * se mantiene ese nombre. La migración, cuando se decida, es mecánica:
 * `npx @next/codemod@canary middleware-to-proxy .`
 */

import type { NextRequest } from "next/server";

import { updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Todo excepto:
     * - _next/static, _next/image (build y optimización de imágenes)
     * - favicon.ico y archivos estáticos de /public
     * Sin estas exclusiones el guard bloquearía CSS, JS e imágenes.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif|ico|css|js|woff|woff2|ttf)$).*)",
  ],
};
