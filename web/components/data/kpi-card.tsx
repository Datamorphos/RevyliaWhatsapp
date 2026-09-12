import * as React from "react"
import { cn } from "cn"

import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
} from "@/components/ui/card"

export type KpiTone = "default" | "warning" | "danger" | "success"

/**
 * Acepta tanto un componente de icono (`icon={CalendarDaysIcon}`) como un
 * elemento ya construido (`icon={<CalendarDaysIcon />}`), porque ambas formas
 * son naturales con `lucide-react`.
 */
export type KpiIcon =
  | React.ComponentType<{ className?: string }>
  | React.ReactNode

const VALUE_TONE: Record<KpiTone, string> = {
  default: "text-foreground",
  warning: "text-warning",
  danger: "text-destructive",
  success: "text-success",
}

const ICON_TONE: Record<KpiTone, string> = {
  default: "text-muted-foreground",
  warning: "text-warning",
  danger: "text-destructive",
  success: "text-success",
}

function renderIcon(icon: KpiIcon | undefined): React.ReactNode {
  if (!icon) return null
  if (typeof icon === "function") {
    const Icon = icon as React.ComponentType<{ className?: string }>
    return <Icon className="size-4" />
  }
  return icon
}

export interface KpiCardProps {
  /** Nombre del indicador, en español. Ej.: "Citas de hoy". */
  label: string
  /** Cifra ya formateada. Usa `formatNumber` de `@/lib/format` para miles. */
  value: React.ReactNode
  /** Aclaración breve: fórmula, estados incluidos o periodo (§5.7). */
  hint?: string
  tone?: KpiTone
  icon?: KpiIcon
  className?: string
}

export function KpiCard({
  label,
  value,
  hint,
  tone = "default",
  icon,
  className,
}: KpiCardProps) {
  const iconNode = renderIcon(icon)

  return (
    <Card size="sm" className={cn("gap-2", className)}>
      <CardHeader>
        <div className="text-sm leading-snug font-medium text-muted-foreground">
          {label}
        </div>
        {iconNode ? (
          <CardAction
            aria-hidden="true"
            className={cn(
              "[&_svg]:size-4 [&_svg]:shrink-0",
              ICON_TONE[tone]
            )}
          >
            {iconNode}
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent>
        <div
          className={cn(
            "font-heading text-2xl leading-none font-semibold tabular-nums",
            VALUE_TONE[tone]
          )}
        >
          {value}
        </div>
        {hint ? (
          <p className="mt-1.5 text-xs leading-snug text-muted-foreground">
            {hint}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}
