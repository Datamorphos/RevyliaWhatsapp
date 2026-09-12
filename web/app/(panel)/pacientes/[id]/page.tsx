import { PageHeader } from "@/components/shell/page-header"
import { QueryMeta } from "@/components/data/query-meta"
import { EmptyState } from "@/components/data/empty-state"
import { ErrorState } from "@/components/data/error-state"
import { StatusBadge } from "@/components/data/status-badge"
import {
  formatBoolean,
  formatCivilDateShort,
  formatPhone,
  orPlaceholder,
} from "@/lib/format"
import type { PatientDetail } from "@/lib/types"

import { safeFetch } from "../../_lib/safe-fetch"
import { TablaCitas } from "../../agenda/_components/tabla-citas"
import { TablaOportunidades } from "../../oportunidades/_components/tabla-oportunidades"

export default async function PacienteDetallePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const result = await safeFetch<PatientDetail>(`/patients/${id}`)

  if (!result.ok) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Paciente" description="Detalle del paciente." />
        <ErrorState
          title="No se pudo cargar el paciente"
          description={result.error.message}
        />
      </div>
    )
  }

  const patient = result.data

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={patient.name}
        description={`${formatPhone(patient.phone)} · última visita: ${formatCivilDateShort(patient.last_visit_date)}`}
      />

      <div className="grid grid-cols-1 gap-4 rounded-lg border p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <div className="text-xs text-muted-foreground">Estado</div>
          <StatusBadge status={patient.status} kind="patient" />
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Último servicio</div>
          <div className="text-sm">{orPlaceholder(patient.last_service)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Consentimiento de marketing</div>
          <div className="text-sm">{formatBoolean(patient.consent_marketing)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Notas</div>
          <div className="text-sm">{orPlaceholder(patient.notes)}</div>
        </div>
      </div>

      <QueryMeta meta={result.meta} />

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Citas</h2>
        {patient.appointments.length === 0 ? (
          <EmptyState
            title="Sin citas"
            description="Este paciente no tiene citas registradas."
          />
        ) : (
          <TablaCitas data={patient.appointments} />
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Oportunidades</h2>
        {patient.opportunities.length === 0 ? (
          <EmptyState
            title="Sin oportunidades"
            description="Este paciente no tiene oportunidades registradas."
          />
        ) : (
          <TablaOportunidades data={patient.opportunities} />
        )}
      </section>
    </div>
  )
}
