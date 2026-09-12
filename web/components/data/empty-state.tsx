import * as React from "react"
import { InboxIcon } from "lucide-react"
import { cn } from "cn"

export interface EmptyStateProps {
  /** Qué no hay. Ej.: "No hay citas en el rango seleccionado". */
  title: string
  /** Opcional: qué puede hacer quien lo lee (cambiar filtros, ampliar fechas). */
  description?: string
  /** Icono alternativo al sobre vacío. */
  icon?: React.ReactNode
  className?: string
}

/**
 * Ausencia de datos: la consulta funcionó y devolvió `data: []` (§4).
 *
 * Es deliberadamente **neutro** — sin rojo, sin icono de alerta, sin botón de
 * reintentar — para que no se confunda con `<ErrorState />`, que sí indica que
 * la consulta falló.
 */
export function EmptyState({
  title,
  description,
  icon,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border px-6 py-10 text-center",
        className
      )}
    >
      <span
        aria-hidden="true"
        className="text-muted-foreground [&_svg]:size-5"
      >
        {icon ?? <InboxIcon />}
      </span>
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? (
        <p className="max-w-prose text-sm text-balance text-muted-foreground">
          {description}
        </p>
      ) : null}
    </div>
  )
}
