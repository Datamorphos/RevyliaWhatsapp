import type { Metadata } from "next";

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { LoginForm } from "./login-form";

export const metadata: Metadata = {
  title: "Acceso — Panel Revylia",
  description: "Acceso al panel interno de la clínica.",
};

/** Avisos que el middleware añade como `?motivo=…`. */
const MOTIVOS: Record<string, string> = {
  sesion_requerida: "Inicia sesión para entrar al panel.",
  sesion_vencida: "Tu sesión venció por inactividad. Vuelve a iniciar sesión.",
  sesion_cerrada: "Cerraste la sesión correctamente.",
};

function primerValor(valor: string | string[] | undefined): string | undefined {
  return Array.isArray(valor) ? valor[0] : valor;
}

export default async function LoginPage({
  searchParams,
}: {
  // En Next.js 16 `searchParams` es una promesa.
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const motivo = primerValor(params.motivo);
  const aviso = motivo ? MOTIVOS[motivo] : undefined;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Panel Revylia</CardTitle>
        <CardDescription>
          Entra con el correo y la contraseña de tu cuenta de la clínica.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {aviso ? (
          <p
            aria-live="polite"
            className="rounded-md border border-border bg-muted px-3 py-2 text-sm text-muted-foreground"
          >
            {aviso}
          </p>
        ) : null}

        <LoginForm next={primerValor(params.next)} />
      </CardContent>

      <CardFooter>
        {/* Decisión de producto: acceso solo por invitación. Sin registro público. */}
        <p className="text-xs text-muted-foreground">
          El acceso es solo por invitación. Si necesitas una cuenta o perdiste tu contraseña,
          solicítalo a la administración de la clínica.
        </p>
      </CardFooter>
    </Card>
  );
}
