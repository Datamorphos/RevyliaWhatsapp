import { RevyliaCopilotSidebarDemo } from "./copilot-sidebar-demo";
import { RevyliaCopilotSidebarLive } from "./copilot-sidebar-live";

/**
 * Sidebar del copiloto del panel — punto de entrada (Server Component, sin
 * "use client" a propósito).
 *
 * Decide en el servidor, antes de enviar nada al cliente, si hay un agente
 * real detrás de `AGENT_URL`:
 * - Configurada: sidebar funcional conectado al runtime real de CopilotKit
 *   (`copilot-sidebar-live.tsx`).
 * - No configurada (demo, sin backend Python, sin clave de modelo, etc.):
 *   panel de demostración, estático y honesto — sin CopilotKit, sin
 *   contexto, sin peticiones de red (`copilot-sidebar-demo.tsx`). Nunca
 *   simula ni inventa una respuesta del asistente.
 *
 * Debe montarse DENTRO de `<CopilotProvider>` en
 * `web/app/(panel)/layout.tsx`. No importa nada del shell del panel
 * (`web/components/shell/**`) para no acoplarse a A3/A5.
 */
export function RevyliaCopilotSidebar() {
  const agentConfigured = Boolean(process.env.AGENT_URL?.trim());

  if (!agentConfigured) {
    return <RevyliaCopilotSidebarDemo />;
  }

  return <RevyliaCopilotSidebarLive />;
}
