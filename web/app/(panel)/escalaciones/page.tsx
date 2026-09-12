import Link from "next/link"

import { PageHeader } from "@/components/shell/page-header"
import { QueryMeta } from "@/components/data/query-meta"
import { EmptyState } from "@/components/data/empty-state"
import { ErrorState } from "@/components/data/error-state"
import { Label } from "@/components/ui/label"
import type { Escalation } from "@/lib/types"

import { safeFetch } from "../_lib/safe-fetch"
import { TablaEscalaciones } from "./_components/tabla-escalaciones"

const ESTADOS = [
  { value: "", label: "Todos" },
  { value: "pending", label: "Pendiente" },
  { value: "in_progress", label: "En proceso" },
  { value: "resolved", label: "Resuelta" },
]

const PRIORIDADES = [
  { value: "", label: "Todas" },
  { value: "urgent", label: "Urgente" },
  { value: "high", label: "Alta" },
  { value: "medium", label: "Media" },
  { value: "low", label: "Baja" },
]

const LIMIT = 25

type SearchParams = Record<string, string | string[] | undefined>

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default async function EscalacionesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const status = first(sp.status)
  const priority = first(sp.priority)
  const offset = Number(first(sp.offset) ?? "0") || 0

  const result = await safeFetch<Escalation[]>("/escalations", {
    status,
    priority,
    limit: LIMIT,
    offset,
  })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Escalaciones"
        description="Ordenadas por prioridad y luego por fecha, tal como las devuelve la API — no se reordenan en el navegador. Las urgentes se destacan explícitamente."
      />

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
            className="h-9 rounded-md border bg-background px-3 text-sm"
          >
            {ESTADOS.map((e) => (
              <option key={e.value} value={e.value}>
                {e.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="priority">Prioridad</Label>
          <select
            id="priority"
            name="priority"
            defaultValue={priority ?? ""}
            className="h-9 rounded-md border bg-background px-3 text-sm"
          >
            {PRIORIDADES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          className="h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
        >
          Filtrar
        </button>
      </form>

      {!result.ok ? (
        <ErrorState
          title="No se pudieron cargar las escalaciones"
          description={result.error.message}
        />
      ) : result.data.length === 0 ? (
        <EmptyState
          title="No hay escalaciones"
          description="No se encontraron escalaciones para los filtros seleccionados."
        />
      ) : (
        <>
          <TablaEscalaciones data={result.data} />
          <div className="flex items-center justify-between">
            <QueryMeta meta={result.meta} />
            <div className="flex gap-2 text-sm">
              {offset > 0 && (
                <Link
                  className="underline"
                  href={{
                    pathname: "/escalaciones",
                    query: { status, priority, offset: Math.max(0, offset - LIMIT) },
                  }}
                >
                  Anterior
                </Link>
              )}
              {offset + LIMIT < (result.meta.total ?? 0) && (
                <Link
                  className="underline"
                  href={{
                    pathname: "/escalaciones",
                    query: { status, priority, offset: offset + LIMIT },
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
