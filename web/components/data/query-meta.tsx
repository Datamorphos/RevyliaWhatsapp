"use client"

import * as React from "react"
import { ClockIcon, DatabaseIcon, FilterIcon, TriangleAlertIcon } from "lucide-react"
import { cn } from "cn"

import {
  formatFilterValue,
  formatNumber,
  formatRelative,
  formatTimestamp,
  toISOAttribute,
} from "@/lib/format"

/**
 * `meta` de la envoltura de respuesta (§4). Solo `source` y `generated_at` son
 * obligatorios; el resto se muestra si viene. Se declara aquí de forma
 * estructural en vez de importar `@/lib/types` (propiedad de A4) para que este
 * componente compile por sí solo; la forma es la misma, así que el tipo de A4
 * es asignable.
 */
export interface QueryMetaValue {
  /** Ej.: `"revylia.patients"` o `"config:CLINIC_KNOWLEDGE"`. */
  source: string
  /** ISO-8601 UTC. Se muestra convertido a `America/Bogota`. */
  generated_at: string
  filters?: Record<string, unknown> | null
  limit?: number | null
  offset?: number | null
  total?: number | null
  next_cursor?: string | null
  /** `/catalog` lo marca: es configuración sin validar (§5.6). */
  pending_validation?: boolean
}

export interface QueryMetaProps {
  meta: QueryMetaValue
  className?: string
}

function activeFilters(
  filters: QueryMetaValue["filters"]
): Array<[string, unknown]> {
  if (!filters) return []
  return Object.entries(filters).filter(
    ([, value]) => value !== null && value !== undefined && value !== ""
  )
}

/**
 * Procedencia de los datos mostrados: fuente, filtros aplicados y momento de la
 * consulta. Es un requisito de producto, no adorno: cada cifra del panel tiene
 * que poder contrastarse contra la misma consulta.
 *
 * El tiempo relativo ("hace 2 minutos") se calcula solo tras el montaje: en el
 * servidor el reloj es otro y la hidratación no coincidiría. La hora absoluta
 * en Bogotá se renderiza siempre.
 */
export function QueryMeta({ meta, className }: QueryMetaProps) {
  const [relative, setRelative] = React.useState<string | null>(null)

  React.useEffect(() => {
    const update = () => setRelative(formatRelative(meta.generated_at))
    update()
    const timer = window.setInterval(update, 60_000)
    return () => window.clearInterval(timer)
  }, [meta.generated_at])

  const filters = activeFilters(meta.filters)

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground",
        className
      )}
    >
      <span className="inline-flex items-center gap-1.5">
        <DatabaseIcon aria-hidden="true" className="size-3.5 shrink-0" />
        <span className="sr-only">Fuente de los datos:</span>
        <span className="font-mono">{meta.source}</span>
      </span>

      {filters.length > 0 ? (
        <span className="inline-flex flex-wrap items-center gap-1.5">
          <FilterIcon aria-hidden="true" className="size-3.5 shrink-0" />
          <span className="sr-only">Filtros aplicados:</span>
          {filters.map(([key, value], index) => (
            <span key={key}>
              <span className="font-mono">{key}</span>
              {": "}
              <span className="text-foreground">{formatFilterValue(value)}</span>
              {index < filters.length - 1 ? "," : null}
            </span>
          ))}
        </span>
      ) : null}

      <span className="inline-flex items-center gap-1.5">
        <ClockIcon aria-hidden="true" className="size-3.5 shrink-0" />
        <span className="sr-only">Momento de la consulta:</span>
        <time dateTime={toISOAttribute(meta.generated_at)}>
          {formatTimestamp(meta.generated_at)}
        </time>
        {relative ? <span>({relative})</span> : null}
      </span>

      {typeof meta.total === "number" ? (
        <span>
          {formatNumber(meta.total)}{" "}
          {meta.total === 1 ? "registro" : "registros"}
        </span>
      ) : null}

      {meta.pending_validation ? (
        <span className="inline-flex items-center gap-1.5 text-warning">
          <TriangleAlertIcon aria-hidden="true" className="size-3.5 shrink-0" />
          Configuración pendiente de validar
        </span>
      ) : null}
    </div>
  )
}
