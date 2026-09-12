import type { Metadata } from "next";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getPanelUser } from "@/lib/supabase/server";

import { cerrarSesion } from "../actions";

export const metadata: Metadata = {
  title: "Sin acceso — Panel Revylia",
  description: "Tu cuenta aún no tiene habilitado el panel.",
};

/**
 * Usuario autenticado pero **sin** `app_metadata.revylia_panel === true` (§2).
 * La habilitación la concede la administración; el usuario no puede dársela.
 */
export default async function SinAccesoPage() {
  const { user } = await getPanelUser();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Tu cuenta aún no tiene acceso</CardTitle>
        <CardDescription>
          Iniciaste sesión correctamente, pero el panel todavía no está habilitado para esta
          cuenta.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-3 text-sm text-muted-foreground">
        {user?.email ? (
          <p>
            Sesión iniciada como <span className="font-medium text-foreground">{user.email}</span>.
          </p>
        ) : null}

        <p>
          Pide a la administración de la clínica que habilite el panel para tu cuenta. La
          habilitación se otorga desde la administración de Supabase; no puede activarse desde
          aquí.
        </p>

        <p>Cuando te habiliten, cierra sesión y vuelve a entrar para que se aplique el cambio.</p>
      </CardContent>

      <CardFooter>
        <form action={cerrarSesion} className="w-full">
          <Button type="submit" variant="outline" className="w-full">
            Cerrar sesión
          </Button>
        </form>
      </CardFooter>
    </Card>
  );
}
