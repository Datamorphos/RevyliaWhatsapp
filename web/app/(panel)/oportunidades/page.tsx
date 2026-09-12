import Link from "next/link"

import { PageHeader } from "@/components/shell/page-header"
import { QueryMeta } from "@/components/data/query-meta"
import { EmptyState } from "@/components/data/empty-state"
import { ErrorState } from "@/components/data/error-state"
import { Label } from "@/components/ui/label"
import type { Opportunity } from "@/lib/types"

import { safeFetch } from "../_lib/safe-fetch"
import { TablaOportunidades } from "./_components/tabla-oportunidades"

const ESTADOS = [
  { value: "", label: "Todas" },
  { value: "open", label: "Abierta" },
  { value: "contacted", label: "Contactada" },
  { value: "won", label: "Ganada" },
  { value: "lost", label: "Perdida" },
  { value: "discarded", label: "Descartada" },
]

const LIMIT = 25

type SearchParams = Record<string, string | string[] | undefined>

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default async function OportunidadesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const status = first(sp.status)
  const minScore = first(sp.min_score)
  const offset = Number(first(sp.offset) ?? "0") || 0

  const result = await safeFetch<Opportunity[]>("/opportunities", {
    status,
    min_score: minScore ? Number(minScore) : undefined,
    limit: LIMIT,
    offset,
  })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Oportunidades"
        description="Ordenadas por score de mayor a menor. Algunas oportunidades no tienen paciente asociado en el sistema: se muestran con el nombre o teléfono sueltos que se registraron en su momento."
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
          <Label htmlFor="min_score">Score mínimo</Label>
          <input
            id="min_score"
            name="min_score"
            type="number"
            min={0}
            max={100}
            defaultValue={minScore ?? ""}
            className="h-9 w-28 rounded-md border bg-background px-3 text-sm"
          />
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
          title="No se pudieron cargar las oportunidades"
          description={result.error.message}
        />
      ) : result.data.length === 0 ? (
        <EmptyState
          title="No hay oportunidades"
          description="No se encontraron oportunidades para los filtros seleccionados."
        />
      ) : (
        <>
          <TablaOportunidades data={result.data} />
          <div className="flex items-center justify-between">
            <QueryMeta meta={result.meta} />
            <div className="flex gap-2 text-sm">
              {offset > 0 && (
                <Link
                  className="underline"
                  href={{
                    pathname: "/oportunidades",
                    query: {
                      status,
                      min_score: minScore,
                      offset: Math.max(0, offset - LIMIT),
                    },
                  }}
                >
                  Anterior
                </Link>
              )}
              {offset + LIMIT < (result.meta.total ?? 0) && (
                <Link
                  className="underline"
                  href={{
                    pathname: "/oportunidades",
                    query: { status, min_score: minScore, offset: offset + LIMIT },
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
