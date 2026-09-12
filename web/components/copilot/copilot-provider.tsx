import type { ReactNode } from "react";
import { CopilotProviderClient } from "./copilot-provider-client";

/**
 * Punto de entrada del copiloto para el resto del panel.
 *
 * Este archivo NO lleva "use client" a propósito: es un Server Component
 * que decide, en el servidor y antes de enviar nada al navegador, si el
 * agente de consulta está configurado (`AGENT_URL` definida).
 *
 * - Configurada: monta el runtime real de CopilotKit
 *   (`copilot-provider-client.tsx`, que sí es "use client").
 * - No configurada (demo, entorno sin backend Python, `AGENT_URL` vacía,
 *   etc.): renderiza `children` tal cual, SIN montar CopilotKit. Cero
 *   peticiones de red, cero contexto de CopilotKit, cero riesgo de errores
 *   de hidratación. El resto del panel sigue funcionando de forma
 *   completamente independiente del copiloto — es un criterio de
 *   aceptación del plan, no un detalle cosmético.
 *
 * `process.env.AGENT_URL` se lee SOLO aquí (módulo de servidor, sin
 * "use client" y sin prefijo NEXT_PUBLIC_): nunca llega al bundle del
 * navegador. Ver docs/CONTRACT_PANEL.md §1.
 */
export function CopilotProvider({ children }: { children: ReactNode }) {
  const agentConfigured = Boolean(process.env.AGENT_URL?.trim());

  if (!agentConfigured) {
    return <>{children}</>;
  }

  return <CopilotProviderClient>{children}</CopilotProviderClient>;
}
