"use client"

import Link from "next/link"

import { DataTable, type PanelColumnDef } from "@/components/data/data-table"
import { StatusBadge } from "@/components/data/status-badge"
import { formatCivilDate, formatTime } from "@/lib/format"
import type { Appointment } from "@/lib/types"

const columns: PanelColumnDef<Appointment>[] = [
  {
    accessorKey: "patient_name",
    header: "Paciente",
    cell: ({ row }) => (
      <Link
        href={`/pacientes/${row.original.patient_id}`}
        className="font-medium hover:underline"
      >
        {row.original.patient_name}
      </Link>
    ),
  },
  {
    accessorKey: "service",
    header: "Servicio",
  },
  {
    accessorKey: "appointment_date",
    header: "Fecha",
    cell: ({ row }) => formatCivilDate(row.original.appointment_date),
  },
  {
    accessorKey: "appointment_time",
    header: "Hora",
    cell: ({ row }) => formatTime(row.original.appointment_time),
  },
  {
    accessorKey: "status",
    header: "Estado",
    cell: ({ row }) => (
      <StatusBadge status={row.original.status} kind="appointment" />
    ),
  },
]

export function TablaCitas({ data }: { data: Appointment[] }) {
  return (
    <DataTable
      columns={columns}
      data={data}
      emptyMessage="No hay citas para los filtros seleccionados."
    />
  )
}
