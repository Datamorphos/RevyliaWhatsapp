"use client"

import * as React from "react"
import { RefreshCwIcon, TriangleAlertIcon } from "lucide-react"
import { cn } from "cn"

import { Button } from "@/components/ui/button"

export interface ErrorStateProps {
  /** Qué falló. Ej.: "No se pudo consultar la agenda". */
  title: string
  /** Mensaje del error (`error.message` de la envoltura §4), ya legible. */
  description?: string
  /** Si se pasa, se muestra el botón "Reintentar". */
  onRetry?: () => void
  className?: string
}

/**
 * Fallo de consulta: `503 upstream_unavailable` u otro error de la API (§4).
 *
 * Se distingue de `<EmptyState />` en tres señales simultáneas —color de
 * destructivo, icono de alerta y acción de reintento— porque el plan exige no
 * confundir "no hay datos" con "no pudimos leer los datos". `role="alert"` hace
 * que los lectores de pantalla lo anuncien al aparecer.
 */
export function ErrorState({
  title,
  description,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-1.5 rounded-xl border border-destructive/30 bg-destructive/5 px-6 py-8 text-center dark:bg-destructive/10",
        className
      )}
    >
      <span
        aria-hidden="true"
        className="mb-1 flex size-9 items-center justify-center rounded-full bg-destructive/10 text-destructive dark:bg-destructive/20"
      >
        <TriangleAlertIcon className="size-4" />
      </span>
      <p className="text-sm font-medium text-destructive">{title}</p>
      {description ? (
        <p className="max-w-prose text-sm text-balance text-muted-foreground">
          {description}
        </p>
      ) : null}
      {onRetry ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={onRetry}
        >
          <RefreshCwIcon aria-hidden="true" />
          Reintentar
        </Button>
      ) : null}
    </div>
  )
}
