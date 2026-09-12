import Link from "next/link"

import { PageHeader } from "@/components/shell/page-header"
import { QueryMeta } from "@/components/data/query-meta"
import { EmptyState } from "@/components/data/empty-state"
import { ErrorState } from "@/components/data/error-state"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import type { WhatsappEvent } from "@/lib/types"

import { safeFetch } from "../_lib/safe-fetch"
import { TablaEventos } from "./_components/tabla-eventos"

const ESTADOS = [
  { value: "", label: "Todos" },
  { value: "processing", label: "Procesando" },
  { value: "completed", label: "Completado" },
  { value: "failed", label: "Fallido" },
]

type SearchParams = Record<string, string | string[] | undefined>

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default async function EventosPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const status = first(sp.status)
  const cursor = first(sp.cursor)

  const result = await safeFetch<WhatsappEvent[]>("/events", {
    status,
    cursor,
  })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Monitor de eventos de WhatsApp"
        description="Estado de procesamiento de los mensajes entrantes de WhatsApp."
      />

      {/* `default`, no `destructive`: es una limitación conocida del esquema,
          no un fallo. En rojo se leía como si algo se hubiera roto. */}
      <Alert>
        <AlertTitle>Limitación verificada del esquema</AlertTitle>
        <AlertDescription>
          Estos eventos muestran <strong>estado de procesamiento</strong>, no
          un historial de conversación: solo se registra el resultado técnico
          de cada mensaje entrante. Además <strong>no existe relación directa
          con pacientes</strong> — únicamente se guarda un hash del número de
          origen, nunca el número en texto plano ni un vínculo a un
          paciente concreto.
        </AlertDescription>
      </Alert>

      <form
        method="get"
        className="flex flex-wrap items-end gap-4 rounded-lg border p-4"
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="status">Estado</Label>
          {/* `<select>` nativo a propósito: este formulario se envía por GET
              sin JavaScript (la página es un Server Component). El `Select` de
              shadcn es de cliente y no aporta un valor nativo al envío, así que
              rompería el filtro. Se le dan las clases del `Input` de shadcn
              para que la altura y el borde casen con el resto. */}
          <select
            id="status"
            name="status"
            defaultValue={status ?? ""}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            {ESTADOS.map((e) => (
              <option key={e.value} value={e.value}>
                {e.label}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit">Filtrar</Button>
      </form>

      {!result.ok ? (
        <ErrorState
          title="No se pudieron cargar los eventos"
          description={result.error.message}
        />
      ) : result.data.length === 0 ? (
        <EmptyState
          title="No hay eventos"
          description="No se encontraron eventos para los filtros seleccionados."
        />
      ) : (
        <>
          <TablaEventos data={result.data} />
          <div className="flex items-center justify-between">
            <QueryMeta meta={result.meta} />
            {result.meta.next_cursor && (
              <Link
                className="text-sm underline"
                href={{
                  pathname: "/eventos",
                  query: { status, cursor: result.meta.next_cursor },
                }}
              >
                Siguiente
              </Link>
            )}
          </div>
        </>
      )}
    </div>
  )
}
