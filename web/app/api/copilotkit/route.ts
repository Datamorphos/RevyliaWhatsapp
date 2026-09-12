import { HttpAgent } from "@ag-ui/client";
import {
  CopilotRuntime,
  createCopilotRuntimeHandler,
} from "@copilotkit/runtime/v2";
import type { NextRequest } from "next/server";

import { createClient } from "@/lib/supabase/server";

/**
 * Proxy del copiloto hacia el agente AG-UI de Python (`src/panel_agent/`).
 *
 * `AGENT_URL` se lee EXCLUSIVAMENTE en este módulo de servidor (no tiene
 * prefijo NEXT_PUBLIC_, así que Next.js nunca lo incluye en el bundle del
 * navegador). Ver docs/CONTRACT_PANEL.md §1.
 *
 * SIN valor por defecto, a propósito. Antes había uno (`http://localhost:8000`)
 * que apuntaba al **gateway de WhatsApp**, no al agente: cualquier despliegue
 * que olvidara la variable proxeaba al proceso equivocado y fallaba con un 404
 * difícil de diagnosticar. Ahora, si falta, se responde 503 explícito.
 *
 * URL canónica en desarrollo (ver DEMO.md):
 *     AGENT_URL=http://localhost:8123/agent/revylia_panel
 *
 * SEGURIDAD — corrección de un fallo crítico:
 * este proxy no reenviaba ninguna credencial, y el endpoint AG-UI de Python no
 * exigía ninguna. Como las herramientas del grafo leen toda la clínica, esa
 * combinación exponía pacientes, teléfonos y notas sin autenticación. Ahora se
 * reenvía el `Authorization: Bearer <token>` de la sesión de Supabase y el
 * backend lo verifica por JWKS igual que la API del panel.
 */
const AGENT_URL = process.env.AGENT_URL;

function serviceUnavailable(message: string) {
  return new Response(
    JSON.stringify({ error: { type: "upstream_unavailable", message } }),
    { status: 503, headers: { "content-type": "application/json" } },
  );
}

function unauthorized(message: string) {
  return new Response(
    JSON.stringify({ error: { type: "unauthorized", message } }),
    { status: 401, headers: { "content-type": "application/json" } },
  );
}

export const POST = async (req: NextRequest) => {
  if (!AGENT_URL) {
    return serviceUnavailable(
      "El copiloto no está configurado en este entorno (falta AGENT_URL).",
    );
  }

  // El token se resuelve POR PETICIÓN: no puede vivir en un runtime de módulo
  // compartido entre usuarios. `getSession()` es la única que devuelve el JWT
  // crudo; la autorización real la hace el backend verificando la firma.
  let accessToken: string | null = null;
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getSession();
    accessToken = data.session?.access_token ?? null;
  } catch {
    // Sin Supabase configurado no hay sesión que reenviar.
    accessToken = null;
  }

  if (!accessToken) {
    return unauthorized(
      "Inicia sesión para usar el copiloto.",
    );
  }

  const runtime = new CopilotRuntime({
    agents: {
      // Nombre fijado por el contrato (§6): debe coincidir EXACTAMENTE con el
      // agente expuesto por `ag_ui_langgraph.add_langgraph_fastapi_endpoint` +
      // `copilotkit.LangGraphAGUIAgent` en src/panel_agent/. Agente de solo
      // lectura: ninguna herramienta del grafo escribe datos.
      revylia_panel: new HttpAgent({
        url: AGENT_URL,
        headers: { Authorization: `Bearer ${accessToken}` },
      }),
    },
  });

  // Generación v2 en ambos lados del stack (Next.js aquí, Python en
  // src/panel_agent/). No mezclar con `remoteEndpoints` / `CopilotRuntime` v1.
  const handler = createCopilotRuntimeHandler({
    runtime,
    basePath: "/api/copilotkit",
    mode: "single-route",
  });

  return handler(req);
};
