import * as React from "react"
import { cn } from "cn"

export interface PageHeaderProps {
  /** Nombre del módulo. Se renderiza como el único `<h1>` de la página. */
  title: string
  /** Qué muestra la página y de dónde sale. Una o dos líneas. */
  description?: string
  /** Controles a la derecha: filtros, selector de fechas, acciones de lectura. */
  actions?: React.ReactNode
  className?: string
}

export function PageHeader({
  title,
  description,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6",
        className
      )}
    >
      <div className="min-w-0 space-y-1">
        <h1 className="font-heading text-xl leading-tight font-semibold tracking-tight text-foreground">
          {title}
        </h1>
        {description ? (
          <p className="max-w-prose text-sm text-pretty text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      ) : null}
    </div>
  )
}
