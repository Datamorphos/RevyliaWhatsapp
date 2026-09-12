/**
 * Refresco de sesión y guard de acceso para el middleware (§2).
 *
 * Patrón oficial de `@supabase/ssr`: crear un cliente de servidor con
 * `getAll`/`setAll`, llamar a `getUser()` **antes** de generar la respuesta y
 * devolver siempre la respuesta que lleva las cookies reescritas. Si se pierde
 * esa respuesta, la sesión se cae de forma intermitente.
 *
 * IMPORTANTE (demo): el guard solo actúa si `PANEL_AUTH_ENABLED === "true"`.
 * Por defecto el middleware no protege nada, para poder abrir el panel sin
 * Supabase. En cualquier despliegue con datos reales hay que activarlo.
 * De todos modos el frontend nunca es la única defensa: el backend verifica el
 * JWT por su cuenta vía JWKS (§2).
 */

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { PANEL_FLAG, getSupabaseEnv, isAuthEnabled } from "./env";

/** Rutas accesibles sin sesión válida. */
const LOGIN_PATH = "/login";
const NO_ACCESS_PATH = "/sin-acceso";

/** Prefijos que el guard nunca bloquea (callbacks de auth y recursos públicos). */
const OPEN_PREFIXES = ["/auth", "/api/auth"];

function isOpenPath(pathname: string): boolean {
  return OPEN_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export async function updateSession(request: NextRequest): Promise<NextResponse> {
  let supabaseResponse = NextResponse.next({ request });

  // Modo demo: sin guard. El panel abre directamente.
  if (!isAuthEnabled()) return supabaseResponse;

  const env = getSupabaseEnv();
  if (!env) {
    // Sin configuración de Supabase no se puede validar nada: se deja pasar y se
    // avisa, en vez de dejar la app inaccesible por un fallo de configuración.
    console.warn(
      "[middleware] PANEL_AUTH_ENABLED=true pero faltan NEXT_PUBLIC_SUPABASE_URL/ANON_KEY: el guard queda inactivo.",
    );
    return supabaseResponse;
  }

  const supabase = createServerClient(env.url, env.anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        for (const { name, value } of cookiesToSet) {
          request.cookies.set(name, value);
        }
        supabaseResponse = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          supabaseResponse.cookies.set(name, value, options);
        }
        // Cabeceras anticaché que envía la librería: sin ellas un CDN podría
        // servir la sesión de un usuario a otro.
        for (const [key, value] of Object.entries(headers ?? {})) {
          supabaseResponse.headers.set(key, value);
        }
      },
    },
  });

  // Debe ejecutarse antes de construir cualquier respuesta: si el refresco
  // termina después, las cookies nuevas se pierden.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;
  // §2: la habilitación vive en app_metadata, NUNCA en user_metadata.
  const enabled = user?.app_metadata?.[PANEL_FLAG] === true;

  if (!isOpenPath(pathname)) {
    // 1. Sin sesión → login (salvo que ya esté en login).
    if (!user && pathname !== LOGIN_PATH) {
      return redirectTo(request, supabaseResponse, LOGIN_PATH, {
        motivo: "sesion_requerida",
        next: pathname + request.nextUrl.search,
      });
    }

    // 2. Con sesión pero sin habilitación → /sin-acceso (que sí es alcanzable).
    if (user && !enabled && pathname !== NO_ACCESS_PATH) {
      return redirectTo(request, supabaseResponse, NO_ACCESS_PATH);
    }

    // 3. Con sesión y habilitado, no tiene sentido ver login ni sin-acceso.
    if (user && enabled && (pathname === LOGIN_PATH || pathname === NO_ACCESS_PATH)) {
      return redirectTo(request, supabaseResponse, "/");
    }
  }

  // Respuestas que pueden traer Set-Cookie de sesión no deben cachearse.
  supabaseResponse.headers.set("Cache-Control", "private, no-store");
  return supabaseResponse;
}

/**
 * Redirige conservando las cookies que el refresco de sesión acaba de escribir.
 * Si no se copian, el usuario pierde la sesión recién renovada.
 */
function redirectTo(
  request: NextRequest,
  current: NextResponse,
  pathname: string,
  params?: Record<string, string>,
): NextResponse {
  const url = request.nextUrl.clone();
  url.pathname = pathname;
  url.search = "";
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value) url.searchParams.set(key, value);
    }
  }

  const response = NextResponse.redirect(url);
  for (const cookie of current.cookies.getAll()) {
    response.cookies.set(cookie);
  }
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}
