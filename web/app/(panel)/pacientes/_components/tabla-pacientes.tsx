"use client"

import Link from "next/link"

import { DataTable, type PanelColumnDef } from "@/components/data/data-table"
import { StatusBadge } from "@/components/data/status-badge"
import {
  formatBoolean,
  formatCivilDateShort,
  formatPhone,
  truncate,
} from "@/lib/format"
import type { Patient } from "@/lib/types"

const columns: PanelColumnDef<Patient>[] = [
  {
    accessorKey: "name",
    header: "Paciente",
    cell: ({ row }) => (
      <div className="flex flex-col">
        <Link
          href={`/pacientes/${row.original.id}`}
          className="font-medium hover:underline"
        >
          {row.original.name}
        </Link>
        <span className="text-xs text-muted-foreground">
          {formatPhone(row.original.phone)} · última visita:{" "}
          {formatCivilDateShort(row.original.last_visit_date)}
        </span>
      </div>
    ),
  },
  {
    accessorKey: "last_service",
    header: "Último servicio",
    cell: ({ row }) => row.original.last_service ?? "—",
  },
  {
    accessorKey: "status",
    header: "Estado",
    cell: ({ row }) => (
      <StatusBadge status={row.original.status} kind="patient" />
    ),
  },
  {
    accessorKey: "consent_marketing",
    header: "Consentimiento",
    cell: ({ row }) => formatBoolean(row.original.consent_marketing),
  },
  {
    accessorKey: "notes",
    header: "Notas",
    cell: ({ row }) => (
      <span title={row.original.notes ?? undefined}>
        {truncate(row.original.notes, 60)}
      </span>
    ),
  },
]

export function TablaPacientes({ data }: { data: Patient[] }) {
  return (
    <DataTable
      columns={columns}
      data={data}
      emptyMessage="No hay pacientes para los filtros seleccionados."
    />
  )
}
