import Link from "next/link"

import { PageHeader } from "@/components/shell/page-header"
import { QueryMeta } from "@/components/data/query-meta"
import { EmptyState } from "@/components/data/empty-state"
import { ErrorState } from "@/components/data/error-state"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import type { Patient } from "@/lib/types"

import { safeFetch } from "../_lib/safe-fetch"
import { TablaPacientes } from "./_components/tabla-pacientes"

const ESTADOS = [
  { value: "", label: "Todos" },
  { value: "active", label: "Activo" },
  { value: "inactive", label: "Inactivo" },
]

const CONSENTIMIENTOS = [
  { value: "", label: "Todos" },
  { value: "true", label: "Con consentimiento" },
  { value: "false", label: "Sin consentimiento" },
]

const LIMIT = 25

type SearchParams = Record<string, string | string[] | undefined>

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default async function PacientesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const query = first(sp.query)
  const status = first(sp.status)
  const consent = first(sp.consent)
  const offset = Number(first(sp.offset) ?? "0") || 0

  const result = await safeFetch<Patient[]>("/patients", {
    query,
    status,
    consent,
    limit: LIMIT,
    offset,
  })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Pacientes"
        description="Búsqueda por nombre o teléfono. Cuando hay homónimos, el teléfono y la última visita ayudan a distinguirlos."
      />

      <form
        method="get"
        className="flex flex-wrap items-end gap-4 rounded-lg border p-4"
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="query">Nombre o teléfono</Label>
          <input
            id="query"
            name="query"
            type="text"
            defaultValue={query ?? ""}
            placeholder="Ej. Laura Gómez o 3001112233"
            className="h-9 w-64 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </div>
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
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="consent">Consentimiento</Label>
          <select
            id="consent"
            name="consent"
            defaultValue={consent ?? ""}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            {CONSENTIMIENTOS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit">Buscar</Button>
      </form>

      {!result.ok ? (
        <ErrorState
          title="No se pudieron cargar los pacientes"
          description={result.error.message}
        />
      ) : result.data.length === 0 ? (
        <EmptyState
          title="No hay pacientes"
          description="No se encontraron pacientes para los filtros seleccionados."
        />
      ) : (
        <>
          <TablaPacientes data={result.data} />
          <div className="flex items-center justify-between">
            <QueryMeta meta={result.meta} />
            <div className="flex gap-2 text-sm">
              {offset > 0 && (
                <Link
                  className="underline"
                  href={{
                    pathname: "/pacientes",
                    query: {
                      query,
                      status,
                      consent,
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
                    pathname: "/pacientes",
                    query: { query, status, consent, offset: offset + LIMIT },
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
