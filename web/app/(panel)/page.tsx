import { PageHeader } from "@/components/shell/page-header"
import { KpiCard } from "@/components/data/kpi-card"
import { QueryMeta } from "@/components/data/query-meta"
import { ErrorState } from "@/components/data/error-state"
import type { Summary } from "@/lib/types"

import { safeFetch } from "./_lib/safe-fetch"

type Tone = "default" | "warning" | "danger" | "success"

type KpiKey = keyof Summary

const KPI_DEFS: { key: KpiKey; label: string; tone?: (value: number) => Tone }[] = [
  { key: "patients_total", label: "Pacientes totales" },
  { key: "patients_active", label: "Pacientes activos" },
  { key: "patients_inactive", label: "Pacientes inactivos" },
  {
    key: "patients_recoverable",
    label: "Pacientes recuperables",
    tone: (v) => (v > 0 ? "warning" : "default"),
  },
  { key: "appointments_today", label: "Citas hoy" },
  { key: "appointments_next_7d", label: "Citas próximos 7 días" },
  {
    key: "appointments_cancelled_30d",
    label: "Citas canceladas (30 días)",
    tone: (v) => (v > 0 ? "warning" : "default"),
  },
  { key: "opportunities_open", label: "Oportunidades abiertas" },
  {
    key: "escalations_pending",
    label: "Escalaciones pendientes",
    tone: (v) => (v > 0 ? "warning" : "default"),
  },
  {
    key: "escalations_urgent_pending",
    label: "Escalaciones urgentes pendientes",
    tone: (v) => (v > 0 ? "danger" : "default"),
  },
  { key: "recovery_drafts", label: "Borradores de recuperación" },
  { key: "events_24h_total", label: "Eventos de WhatsApp (24h)" },
  {
    key: "events_24h_failed",
    label: "Eventos fallidos (24h)",
    tone: (v) => (v > 0 ? "danger" : "default"),
  },
]

export default async function ResumenPage() {
  const result = await safeFetch<Summary>("/summary")

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Resumen operativo"
        description="Indicadores deterministas calculados en el servidor. Cada tarjeta muestra entre paréntesis la fórmula exacta usada para su cálculo, tal como la documenta el contrato del panel."
      />

      {!result.ok ? (
        <ErrorState
          title="No se pudo cargar el resumen"
          description={result.error.message}
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {KPI_DEFS.map(({ key, label, tone }) => {
              const kpi = result.data[key]
              return (
                <KpiCard
                  key={key}
                  label={label}
                  value={kpi.value}
                  hint={kpi.formula}
                  tone={tone ? tone(kpi.value) : "default"}
                />
              )
            })}
          </div>
          <QueryMeta meta={result.meta} />
        </>
      )}
    </div>
  )
}
