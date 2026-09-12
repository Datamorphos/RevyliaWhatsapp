"use client"

import Link from "next/link"

import { DataTable, type PanelColumnDef } from "@/components/data/data-table"
import { StatusBadge } from "@/components/data/status-badge"
import { formatPhone, formatScore, formatTimestamp } from "@/lib/format"
import type { Opportunity } from "@/lib/types"

const columns: PanelColumnDef<Opportunity>[] = [
  {
    accessorKey: "patient_name",
    header: "Paciente",
    cell: ({ row }) => {
      const { patient_id, patient_name, phone } = row.original
      if (patient_id) {
        return (
          <Link
            href={`/pacientes/${patient_id}`}
            className="font-medium hover:underline"
          >
            {patient_name ?? "Ver paciente"}
          </Link>
        )
      }
      if (patient_name || phone) {
        return (
          <div className="flex flex-col">
            {patient_name && <span>{patient_name}</span>}
            {phone && (
              <span className="text-xs text-muted-foreground">
                {formatPhone(phone)}
              </span>
            )}
          </div>
        )
      }
      return <span className="text-muted-foreground">Sin paciente asociado</span>
    },
  },
  {
    accessorKey: "reason",
    header: "Motivo",
    cell: ({ row }) => <span>{row.original.reason}</span>,
  },
  {
    accessorKey: "score",
    header: "Score",
    cell: ({ row }) => formatScore(row.original.score),
  },
  {
    accessorKey: "status",
    header: "Estado",
    cell: ({ row }) => (
      <StatusBadge status={row.original.status} kind="opportunity" />
    ),
  },
  {
    accessorKey: "created_at",
    header: "Creada",
    cell: ({ row }) => formatTimestamp(row.original.created_at),
  },
]

export function TablaOportunidades({ data }: { data: Opportunity[] }) {
  return (
    <DataTable
      columns={columns}
      data={data}
      emptyMessage="No hay oportunidades para los filtros seleccionados."
    />
  )
}
