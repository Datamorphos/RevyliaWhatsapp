"use client";

import { useState } from "react";
import { MessageCircle, X } from "lucide-react";

const SUGERENCIAS_DEMO = [
  "¿Cuántas citas hay hoy?",
  "Muéstrame las escalaciones urgentes",
  "¿Qué pacientes son recuperables?",
];

/**
 * Panel de demostración del copiloto: se muestra cuando `AGENT_URL` NO está
 * configurada (ver `copilot-sidebar.tsx`), típicamente en una demo sin base
 * de datos ni clave de modelo garantizadas.
 *
 * Deliberadamente NO importa nada de CopilotKit ni hace peticiones de red:
 * es un componente 100% estático/local (solo `useState` para abrir/cerrar).
 * Comunica la propuesta de producto — título, alcance, sugerencias — sin
 * simular jamás una respuesta real del asistente. El aviso de "pendiente de
 * conexión" es explícito para no confundir a nadie en la demo.
 */
export function RevyliaCopilotSidebarDemo() {
  // Cerrado por defecto: abierto tapaba las tarjetas del resumen.
  // El usuario lo abre con el botón flotante cuando quiere mostrarlo.
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="copiloto-demo-panel"
        className="fixed bottom-5 right-5 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105"
      >
        {open ? <X className="size-5" /> : <MessageCircle className="size-5" />}
        <span className="sr-only">
          {open ? "Cerrar copiloto" : "Abrir copiloto"}
        </span>
      </button>

      {open ? (
        <aside
          id="copiloto-demo-panel"
          className="fixed bottom-20 right-5 z-50 flex w-[min(22rem,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-xl border border-border bg-card text-card-foreground shadow-xl"
        >
          <header className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Copiloto Revylia</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Copiloto en modo demostración — el agente de consulta aún no
              está conectado.
            </p>
          </header>

          <div className="flex flex-col gap-3 px-4 py-3">
            <p className="text-sm text-foreground">
              Cuando esté conectado, podrás consultar, resumir y filtrar la
              información del panel (pacientes, citas, escalaciones,
              oportunidades) en lenguaje natural. Es de{" "}
              <strong>solo lectura</strong>: nunca escribe, envía mensajes de
              WhatsApp ni modifica datos.
            </p>

            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">
                Ejemplos de lo que podrás preguntar:
              </p>
              <ul className="flex flex-col gap-1.5">
                {SUGERENCIAS_DEMO.map((sugerencia) => (
                  <li
                    key={sugerencia}
                    className="cursor-not-allowed rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-muted-foreground"
                    title="Disponible cuando el agente esté conectado"
                  >
                    {sugerencia}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <footer className="border-t border-border px-4 py-2.5">
            <p className="text-[11px] text-muted-foreground">
              Solo lectura: nunca modifica datos ni envía mensajes a
              pacientes.
            </p>
          </footer>
        </aside>
      ) : null}
    </>
  );
}
