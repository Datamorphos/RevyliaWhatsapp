"use client";

import { Component, type ReactNode } from "react";
import {
  CopilotSidebar,
  useConfigureSuggestions,
} from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";

const MENSAJE_BIENVENIDA =
  "Soy el copiloto del panel Revylia. Puedo consultar, resumir y filtrar la " +
  "información que ya ves aquí: pacientes, citas, escalaciones, oportunidades " +
  "y eventos. Soy de SOLO LECTURA — no escribo en la base de datos, no envío " +
  "mensajes de WhatsApp a pacientes ni modifico ningún registro.";

const AVISO_SOLO_LECTURA =
  "Solo lectura: nunca modifica datos ni envía mensajes a pacientes.";

/**
 * Sugerencias iniciales visibles antes del primer mensaje. Se registran vía
 * `useConfigureSuggestions` (reemplazo v2 de `useCopilotChatSuggestions`) en
 * lugar de generarse dinámicamente, para no depender de una llamada al
 * modelo solo para poblar los chips de arranque.
 */
function SugerenciasIniciales() {
  useConfigureSuggestions({
    suggestions: [
      { title: "Citas de hoy", message: "¿Cuántas citas hay hoy?" },
      {
        title: "Escalaciones urgentes",
        message: "Muéstrame las escalaciones urgentes",
      },
      {
        title: "Pacientes recuperables",
        message: "¿Qué pacientes son recuperables?",
      },
    ],
    available: "before-first-message",
  });

  return null;
}

/**
 * Red de seguridad adicional: si el sidebar del copiloto lanzara una
 * excepción al renderizar (más allá de los errores de conexión que
 * CopilotKit ya maneja internamente vía `onError`/banner), el resto del
 * panel debe seguir siendo usable. Este límite de errores oculta solo el
 * copiloto, nunca la página completa.
 */
class CopilotSidebarBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error("[copilotkit] el sidebar no pudo renderizarse:", error);
  }

  render() {
    if (this.state.hasError) {
      return null;
    }

    return this.props.children;
  }
}

/**
 * Sidebar del copiloto conectado al runtime real (solo se monta cuando
 * `AGENT_URL` está configurada; ver `copilot-sidebar.tsx`). Todo el texto
 * visible está en español.
 */
export function RevyliaCopilotSidebarLive() {
  return (
    <CopilotSidebarBoundary>
      <SugerenciasIniciales />
      <CopilotSidebar
        labels={{
          modalHeaderTitle: "Copiloto Revylia",
          chatInputPlaceholder: "Pregunta por pacientes, citas, escalaciones…",
          welcomeMessageText: MENSAJE_BIENVENIDA,
          chatDisclaimerText: AVISO_SOLO_LECTURA,
        }}
      />
    </CopilotSidebarBoundary>
  );
}
