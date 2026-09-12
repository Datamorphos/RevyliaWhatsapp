"use client"

import Link from "next/link"

import { DataTable, type PanelColumnDef } from "@/components/data/data-table"
import { StatusBadge } from "@/components/data/status-badge"
import { formatBoolean, formatTimestamp, truncate } from "@/lib/format"
import type { RecoveryMessage } from "@/lib/types"

const columns: PanelColumnDef<RecoveryMessage>[] = [
  {
    accessorKey: "patient_id",
    header: "Paciente",
    cell: ({ row }) => (
      <Link
        href={`/pacientes/${row.original.patient_id}`}
        className="font-medium hover:underline"
      >
        {row.original.patient_name ?? "Ver paciente"}
      </Link>
    ),
  },
  {
    accessorKey: "message",
    header: "Mensaje",
    cell: ({ row }) => (
      <span title={row.original.message}>
        {truncate(row.original.message, 100)}
      </span>
    ),
  },
  {
    accessorKey: "approval_required",
    header: "Requiere aprobación",
    cell: ({ row }) => formatBoolean(row.original.approval_required),
  },
  {
    accessorKey: "status",
    header: "Estado",
    cell: ({ row }) => (
      <StatusBadge status={row.original.status} kind="recovery" />
    ),
  },
  {
    accessorKey: "created_at",
    header: "Creado",
    cell: ({ row }) => formatTimestamp(row.original.created_at),
  },
]

export function TablaRecuperacion({ data }: { data: RecoveryMessage[] }) {
  return (
    <DataTable
      columns={columns}
      data={data}
      emptyMessage="No hay mensajes de recuperación para los filtros seleccionados."
    />
  )
}
