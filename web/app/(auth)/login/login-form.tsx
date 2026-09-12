"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";

/** Traduce los errores de Supabase Auth a mensajes claros en español. */
function mensajeDeError(codigo: string | undefined, mensaje: string): string {
  const texto = `${codigo ?? ""} ${mensaje}`.toLowerCase();

  if (texto.includes("invalid login credentials") || texto.includes("invalid_credentials")) {
    return "Correo o contraseña incorrectos. Revisa los datos e intenta de nuevo.";
  }
  if (texto.includes("email not confirmed") || texto.includes("email_not_confirmed")) {
    return "Tu cuenta aún no está confirmada. Revisa el correo de invitación.";
  }
  if (texto.includes("rate limit") || texto.includes("too many")) {
    return "Demasiados intentos. Espera unos minutos antes de volver a intentarlo.";
  }
  if (texto.includes("user is banned") || texto.includes("user_banned")) {
    return "Esta cuenta está deshabilitada. Contacta a la administración de la clínica.";
  }
  if (texto.includes("failed to fetch") || texto.includes("network")) {
    return "No se pudo conectar con el servicio de acceso. Revisa tu conexión.";
  }
  return "No se pudo iniciar sesión. Intenta de nuevo o contacta a la administración.";
}

/** Solo se aceptan rutas internas: evita redirecciones abiertas hacia otro dominio. */
function destinoSeguro(next: string | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return "/";
  return next;
}

export function LoginForm({ next }: { next?: string }) {
  const router = useRouter();
  const [correo, setCorreo] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setEnviando(true);

    try {
      const supabase = createClient();
      const { error: authError } = await supabase.auth.signInWithPassword({
        email: correo.trim(),
        password: contrasena,
      });

      if (authError) {
        setError(mensajeDeError(authError.code, authError.message));
        setEnviando(false);
        return;
      }

      // `refresh()` obliga al servidor a releer la sesión recién creada.
      router.replace(destinoSeguro(next));
      router.refresh();
    } catch {
      setError(
        "El acceso no está configurado en este entorno. Contacta a la administración de la clínica.",
      );
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="space-y-2">
        <Label htmlFor="correo">Correo electrónico</Label>
        <Input
          id="correo"
          name="correo"
          type="email"
          autoComplete="username"
          inputMode="email"
          required
          placeholder="nombre@clinica.com"
          value={correo}
          onChange={(event) => setCorreo(event.target.value)}
          disabled={enviando}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="contrasena">Contraseña</Label>
        <Input
          id="contrasena"
          name="contrasena"
          type="password"
          autoComplete="current-password"
          required
          value={contrasena}
          onChange={(event) => setContrasena(event.target.value)}
          disabled={enviando}
        />
      </div>

      {error ? (
        <p
          role="alert"
          aria-live="polite"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {error}
        </p>
      ) : null}

      <Button type="submit" className="w-full" disabled={enviando}>
        {enviando ? "Entrando…" : "Entrar"}
      </Button>
    </form>
  );
}
