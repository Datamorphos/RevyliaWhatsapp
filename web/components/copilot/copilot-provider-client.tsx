"use client";

import type { ReactNode } from "react";
import { CopilotKit } from "@copilotkit/react-core/v2";

/**
 * Mount real del runtime de CopilotKit v2.
 *
 * Solo se renderiza cuando `AGENT_URL` está configurada (la decisión se
 * toma en el Server Component `copilot-provider.tsx`), así que aquí siempre
 * asumimos que existe un runtime real detrás de `/api/copilotkit`.
 *
 * - `agent="revylia_panel"` activa el "Agent Lock Mode" de CopilotKit: todas
 *   las llamadas del sidebar van a ese único agente. El nombre debe
 *   coincidir EXACTAMENTE con el registrado en `src/panel_agent/` (A2) y
 *   con la clave usada en `web/app/api/copilotkit/route.ts` (A6).
 * - A propósito NO se fija `useSingleEndpoint`: el runtime del servidor usa
 *   `mode: "single-route"`, y fijar `useSingleEndpoint={false}` (pensado
 *   para runtimes multi-route) produciría 404 en la sonda `/info` de
 *   arranque. Sin el prop, el cliente negocia el transporte correcto contra
 *   un handler single-route.
 * - `onError` solo registra en consola. Un fallo de conexión con el agente
 *   (backend caído, timeout, 500, etc.) NUNCA debe lanzar una excepción de
 *   render ni tumbar el panel: CopilotKit ya degrada mostrando un aviso
 *   dentro del propio sidebar en vez de romper el árbol de React.
 */
export function CopilotProviderClient({ children }: { children: ReactNode }) {
  return (
    <CopilotKit
      runtimeUrl="/api/copilotkit"
      agent="revylia_panel"
      onError={(event) => {
        console.error("[copilotkit] error de conexión con el agente:", event);
      }}
    >
      {children}
    </CopilotKit>
  );
}
