"use client"

import { DataTable, type PanelColumnDef } from "@/components/data/data-table"
import { StatusBadge } from "@/components/data/status-badge"
import { formatTimestamp, orPlaceholder, truncate } from "@/lib/format"
import type { WhatsappEvent } from "@/lib/types"

const columns: PanelColumnDef<WhatsappEvent>[] = [
  {
    accessorKey: "message_id",
    header: "ID de mensaje",
    cell: ({ row }) => (
      <span className="font-mono text-xs">{row.original.message_id}</span>
    ),
  },
  {
    accessorKey: "status",
    header: "Estado",
    cell: ({ row }) => <StatusBadge status={row.original.status} kind="event" />,
  },
  {
    accessorKey: "error_type",
    header: "Tipo de error",
    cell: ({ row }) => orPlaceholder(row.original.error_type),
  },
  {
    accessorKey: "received_at",
    header: "Recibido",
    cell: ({ row }) => formatTimestamp(row.original.received_at),
  },
  {
    accessorKey: "processed_at",
    header: "Procesado",
    cell: ({ row }) =>
      row.original.processed_at ? formatTimestamp(row.original.processed_at) : "—",
  },
  {
    accessorKey: "response_text",
    header: "Respuesta",
    cell: ({ row }) => (
      <span title={row.original.response_text ?? undefined}>
        {truncate(row.original.response_text, 80)}
      </span>
    ),
  },
]

export function TablaEventos({ data }: { data: WhatsappEvent[] }) {
  return (
    <DataTable
      columns={columns}
      data={data}
      emptyMessage="No hay eventos de WhatsApp para los filtros seleccionados."
    />
  )
}
