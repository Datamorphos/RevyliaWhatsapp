import * as React from "react"
import { cn } from "cn"

import { Badge } from "@/components/ui/badge"
import { PLACEHOLDER } from "@/lib/format"

/**
 * Tipos de estado del esquema `revylia.*`.
 *
 * `escalation` mapea el vocabulario de **prioridad** (`low|medium|high|urgent`),
 * que es lo que se muestra en la lista de escalaciones (§7). Por robustez
 * también reconoce los valores de `escalations.status`.
 */
export type StatusKind =
  | "appointment"
  | "patient"
  | "opportunity"
  | "escalation"
  | "recovery"
  | "event"

type Tone = "neutral" | "info" | "success" | "warning" | "danger"

type Entry = { label: string; tone: Tone }

/**
 * Solo `patients.status`, `appointments.status`, `escalations.priority` y
 * `whatsapp_inbound_events.status` tienen `CHECK` en `001_business.sql`.
 * `opportunities.status` y `recovery_messages.status` no lo tienen: hoy el
 * código solo escribe `open`, `draft` y `approved`, pero la columna admite
 * cualquier texto. Los valores extra están previstos y, si aun así llega uno
 * desconocido, se muestra el texto crudo en tono neutro (nunca vacío).
 */
const MAPS: Record<StatusKind, Record<string, Entry>> = {
  // CHECK (status IN ('pending','confirmed','cancelled','completed'))
  appointment: {
    pending: { label: "Pendiente", tone: "warning" },
    confirmed: { label: "Confirmada", tone: "success" },
    cancelled: { label: "Cancelada", tone: "danger" },
    completed: { label: "Completada", tone: "neutral" },
  },
  // CHECK (status IN ('active','inactive'))
  patient: {
    active: { label: "Activo", tone: "success" },
    inactive: { label: "Inactivo", tone: "neutral" },
  },
  // Sin CHECK. El agente solo escribe 'open'.
  opportunity: {
    open: { label: "Abierta", tone: "info" },
    contacted: { label: "Contactada", tone: "info" },
    won: { label: "Ganada", tone: "success" },
    lost: { label: "Perdida", tone: "danger" },
    closed: { label: "Cerrada", tone: "neutral" },
    discarded: { label: "Descartada", tone: "neutral" },
  },
  // CHECK (priority IN ('low','medium','high','urgent')) + status sin CHECK.
  escalation: {
    urgent: { label: "Urgente", tone: "danger" },
    high: { label: "Alta", tone: "warning" },
    medium: { label: "Media", tone: "info" },
    low: { label: "Baja", tone: "neutral" },
    pending: { label: "Pendiente", tone: "warning" },
    in_progress: { label: "En proceso", tone: "info" },
    resolved: { label: "Resuelta", tone: "success" },
    dismissed: { label: "Descartada", tone: "neutral" },
  },
  // Sin CHECK. `save_recovery_message` escribe 'draft' o 'approved'.
  recovery: {
    draft: { label: "Borrador", tone: "info" },
    approved: { label: "Aprobado", tone: "success" },
    sent: { label: "Enviado", tone: "neutral" },
    rejected: { label: "Rechazado", tone: "danger" },
    discarded: { label: "Descartado", tone: "neutral" },
  },
  // CHECK (status IN ('processing','completed','failed'))
  event: {
    processing: { label: "Procesando", tone: "warning" },
    completed: { label: "Completado", tone: "success" },
    failed: { label: "Fallido", tone: "danger" },
  },
}

/**
 * `info` no puede quedarse en `outline` (gris): en la columna de prioridad de
 * Escalaciones, "Media" (info) y "Baja" (neutral) se renderizaban idénticas y
 * la escala urgente > alta > media > baja perdía su lectura de un vistazo.
 * Por eso existe el token `--info` en `app/globals.css`.
 */
const TONE_CLASS: Record<Tone, string> = {
  neutral: "",
  info: "bg-info/15 text-info dark:bg-info/20",
  success: "bg-success/15 text-success dark:bg-success/20",
  warning: "bg-warning/15 text-warning dark:bg-warning/20",
  danger: "",
}

const TONE_VARIANT: Record<Tone, "secondary" | "outline" | "destructive"> = {
  neutral: "secondary",
  info: "secondary",
  success: "secondary",
  warning: "secondary",
  danger: "destructive",
}

/** Traduce un estado a su etiqueta en español sin renderizar nada. */
export function statusLabel(
  status: string | null | undefined,
  kind: StatusKind
): string {
  if (!status) return PLACEHOLDER
  return MAPS[kind][status]?.label ?? status
}

export interface StatusBadgeProps {
  status: string | null | undefined
  kind: StatusKind
  className?: string
}

export function StatusBadge({ status, kind, className }: StatusBadgeProps) {
  if (!status) {
    return (
      <span className={cn("text-muted-foreground", className)}>
        {PLACEHOLDER}
      </span>
    )
  }

  const entry: Entry = MAPS[kind][status] ?? { label: status, tone: "neutral" }

  return (
    <Badge
      variant={TONE_VARIANT[entry.tone]}
      className={cn("gap-1.5", TONE_CLASS[entry.tone], className)}
    >
      <span
        aria-hidden="true"
        className="size-1.5 shrink-0 rounded-full bg-current opacity-70"
      />
      {entry.label}
    </Badge>
  )
}
