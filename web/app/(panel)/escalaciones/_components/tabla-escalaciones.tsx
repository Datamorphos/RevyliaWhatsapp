"use client"

import Link from "next/link"

import { DataTable, type PanelColumnDef } from "@/components/data/data-table"
import { StatusBadge } from "@/components/data/status-badge"
import { formatTimestamp } from "@/lib/format"
import type { Escalation } from "@/lib/types"

const columns: PanelColumnDef<Escalation>[] = [
  {
    accessorKey: "patient_id",
    header: "Paciente",
    cell: ({ row }) =>
      row.original.patient_id ? (
        <Link
          href={`/pacientes/${row.original.patient_id}`}
          className="font-medium hover:underline"
        >
          {row.original.patient_name ?? "Ver paciente"}
        </Link>
      ) : (
        <span className="text-muted-foreground">Sin paciente asociado</span>
      ),
  },
  {
    accessorKey: "reason",
    header: "Motivo",
    cell: ({ row }) => <span>{row.original.reason}</span>,
  },
  {
    accessorKey: "priority",
    header: "Prioridad",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <StatusBadge status={row.original.priority} kind="escalation" />
        {row.original.priority === "urgent" && (
          <span className="text-xs font-semibold text-destructive">
            ¡Urgente!
          </span>
        )}
      </div>
    ),
  },
  {
    accessorKey: "status",
    header: "Estado",
    cell: ({ row }) => (
      <StatusBadge status={row.original.status} kind="escalation" />
    ),
  },
  {
    accessorKey: "created_at",
    header: "Creada",
    cell: ({ row }) => formatTimestamp(row.original.created_at),
  },
]

export function TablaEscalaciones({ data }: { data: Escalation[] }) {
  return (
    <DataTable
      columns={columns}
      data={data}
      emptyMessage="No hay escalaciones para los filtros seleccionados."
    />
  )
}
