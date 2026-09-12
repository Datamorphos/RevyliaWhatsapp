"use server";

import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

/**
 * Cierra la sesión y vuelve a `/login`.
 *
 * Se hace en el servidor para que las cookies de sesión se borren de verdad,
 * incluso si el navegador tiene JavaScript deshabilitado.
 */
export async function cerrarSesion() {
  try {
    const supabase = await createClient();
    await supabase.auth.signOut();
  } catch {
    // Sin Supabase configurado no hay sesión que cerrar: igualmente se redirige.
  }

  // `redirect` debe quedar fuera del try: funciona lanzando una excepción interna.
  redirect("/login?motivo=sesion_cerrada");
}
