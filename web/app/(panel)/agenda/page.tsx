import { PageHeader } from "@/components/shell/page-header"
import { QueryMeta } from "@/components/data/query-meta"
import { EmptyState } from "@/components/data/empty-state"
import { ErrorState } from "@/components/data/error-state"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { formatCivilWeekday, formatTime, todayCivilDate } from "@/lib/format"
import type { Appointment, Availability } from "@/lib/types"

import { safeFetch } from "../_lib/safe-fetch"
import { TablaCitas } from "./_components/tabla-citas"

const ESTADOS = [
  { value: "", label: "Todos" },
  { value: "pending", label: "Pendiente" },
  { value: "confirmed", label: "Confirmada" },
  { value: "cancelled", label: "Cancelada" },
  { value: "completed", label: "Completada" },
]

type SearchParams = Record<string, string | string[] | undefined>

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default async function AgendaPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const sp = await searchParams
  const dateFrom = first(sp.date_from)
  const dateTo = first(sp.date_to)
  const status = first(sp.status)
  const availabilityDate = first(sp.availability_date) || todayCivilDate()

  const [appointmentsResult, availabilityResult] = await Promise.all([
    safeFetch<Appointment[]>("/appointments", {
      date_from: dateFrom,
      date_to: dateTo,
      status,
    }),
    safeFetch<Availability>("/availability", { date: availabilityDate }),
  ])

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Agenda"
        description="Citas de la clínica y disponibilidad del día."
      />

      <Alert>
        <AlertTitle>Limitación verificada del esquema</AlertTitle>
        <AlertDescription>
          La agenda usa franjas de <strong>1 hora en punto</strong> y un único
          cupo por clínica, fecha y hora. El esquema no modela profesionales,
          consultorios ni ocupación por duración del servicio: una franja
          ocupada solo indica que ya existe una cita confirmada o pendiente
          en esa hora, no cuántos recursos hay disponibles.
        </AlertDescription>
      </Alert>

      <form
        method="get"
        className="flex flex-wrap items-end gap-4 rounded-lg border p-4"
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="date_from">Desde</Label>
          <input
            id="date_from"
            name="date_from"
            type="date"
            defaultValue={dateFrom ?? ""}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="date_to">Hasta</Label>
          <input
            id="date_to"
            name="date_to"
            type="date"
            defaultValue={dateTo ?? ""}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
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
          <Label htmlFor="availability_date">Disponibilidad del día</Label>
          <input
            id="availability_date"
            name="availability_date"
            type="date"
            defaultValue={availabilityDate}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </div>
        <Button type="submit">Filtrar</Button>
      </form>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Citas</h2>
        {!appointmentsResult.ok ? (
          <ErrorState
            title="No se pudieron cargar las citas"
            description={appointmentsResult.error.message}
          />
        ) : appointmentsResult.data.length === 0 ? (
          <EmptyState
            title="No hay citas"
            description="No hay citas registradas para los filtros seleccionados."
          />
        ) : (
          <>
            <TablaCitas data={appointmentsResult.data} />
            <QueryMeta meta={appointmentsResult.meta} />
          </>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">
          Disponibilidad — {formatCivilWeekday(availabilityDate)}
        </h2>
        {!availabilityResult.ok ? (
          <ErrorState
            title="No se pudo cargar la disponibilidad"
            description={availabilityResult.error.message}
          />
        ) : !availabilityResult.data.is_open ? (
          <EmptyState
            title="Clínica cerrada"
            description="La clínica no atiende ese día (domingo)."
          />
        ) : (
          <>
            {availabilityResult.data.note && (
              <p className="text-sm text-muted-foreground">
                {availabilityResult.data.note}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              {availabilityResult.data.slots.map((slot) => (
                <Badge
                  key={slot.time}
                  variant={slot.available ? "secondary" : "outline"}
                  className={
                    slot.available ? "" : "text-muted-foreground line-through"
                  }
                >
                  {formatTime(slot.time)} ·{" "}
                  {slot.available ? "Disponible" : "Ocupado"}
                </Badge>
              ))}
            </div>
            <QueryMeta meta={availabilityResult.meta} />
          </>
        )}
      </section>
    </div>
  )
}
