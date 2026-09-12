import Link from "next/link"

import { PageHeader } from "@/components/shell/page-header"
import { QueryMeta } from "@/components/data/query-meta"
import { EmptyState } from "@/components/data/empty-state"
import { ErrorState } from "@/components/data/error-state"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import type { RecoveryMessage } from "@/lib/types"

import { safeFetch } from "../_lib/safe-fetch"
import { TablaRecuperacion } from "./_components/tabla-recuperacion"

const ESTADOS = [
  { value: "", label: "Todos" },
  { value: "draft", label: "Borrador" },
  { value: "approved", label: "Aprobado" },
  { value: "sent", label: "Enviado" },
  { value: "rejected", label: "Rechazado" },
  { value: "discarded", label: "Descartado" },
]

const LIMIT = 25

type SearchParams = Record<string, string | string[] | undefined>

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default async function RecuperacionPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const status = first(sp.status)
  const offset = Number(first(sp.offset) ?? "0") || 0

  const result = await safeFetch<RecoveryMessage[]>("/recovery", {
    status,
    limit: LIMIT,
    offset,
  })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Recuperación"
        description="Mensajes de recuperación propuestos por el agente, con su estado y si requieren aprobación humana."
      />

      <Alert>
        <AlertTitle>Este panel es solo de lectura</AlertTitle>
        <AlertDescription>
          Aquí solo se consulta el estado de los mensajes de recuperación. El
          panel <strong>no envía ni aprueba nada</strong>: no existe ninguna
          acción que dispare un mensaje a un paciente desde esta pantalla.
        </AlertDescription>
      </Alert>

      <form
        method="get"
        className="flex flex-wrap items-end gap-4 rounded-lg border p-4"
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="status">Estado</Label>
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
          title="No se pudieron cargar los mensajes de recuperación"
          description={result.error.message}
        />
      ) : result.data.length === 0 ? (
        <EmptyState
          title="No hay mensajes de recuperación"
          description="No se encontraron mensajes para los filtros seleccionados."
        />
      ) : (
        <>
          <TablaRecuperacion data={result.data} />
          <div className="flex items-center justify-between">
            <QueryMeta meta={result.meta} />
            <div className="flex gap-2 text-sm">
              {offset > 0 && (
                <Link
                  className="underline"
                  href={{
                    pathname: "/recuperacion",
                    query: { status, offset: Math.max(0, offset - LIMIT) },
                  }}
                >
                  Anterior
                </Link>
              )}
              {offset + LIMIT < (result.meta.total ?? 0) && (
                <Link
                  className="underline"
                  href={{
                    pathname: "/recuperacion",
                    query: { status, offset: offset + LIMIT },
                  }}
                >
                  Siguiente
                </Link>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
