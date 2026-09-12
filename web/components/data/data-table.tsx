"use client"

import * as React from "react"
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table"
import { InboxIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

/**
 * Tabla del panel sobre `@tanstack/react-table` v8 (la API de los ejemplos de
 * shadcn). Se bajó de v9 a v8 deliberadamente: v9 cambia el constraint de
 * `RowData` y la forma de renderizar celdas, y no compensaba pelearlo.
 *
 * NO se registra ordenación ni paginación de cliente **a propósito**: la API
 * ordena y pagina en el servidor con un orden estable. Ordenar en cliente
 * reordenaría solo la página visible y daría una lectura falsa del conjunto.
 */

/** `ColumnDef` del panel. Los módulos declaran columnas con este tipo. */
export type PanelColumnDef<TData> = ColumnDef<TData, unknown>

/** Helper tipado para declarar columnas con inferencia del valor de celda. */
export function createPanelColumnHelper<TData>() {
  return createColumnHelper<TData>()
}

const SKELETON_ROWS = 5

export interface DataTableProps<TData> {
  columns: Array<PanelColumnDef<TData>>
  data: TData[]
  /** Texto de "sin resultados". Ej.: "No hay citas en este rango." */
  emptyMessage: string
  isLoading?: boolean
  className?: string
}

export function DataTable<TData>({
  columns,
  data,
  emptyMessage,
  isLoading = false,
  className,
}: DataTableProps<TData>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  const headerGroups = table.getHeaderGroups()
  const rows = table.getRowModel().rows
  const columnCount =
    headerGroups[headerGroups.length - 1]?.headers.length ?? columns.length

  return (
    <div
      aria-busy={isLoading}
      className={cn("rounded-xl border border-border bg-card", className)}
    >
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            {headerGroups.map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent">
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className="bg-muted/40 px-3 text-xs font-medium text-muted-foreground first:rounded-tl-xl last:rounded-tr-xl"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>

          <TableBody>
            {isLoading ? (
              Array.from({ length: SKELETON_ROWS }, (_, rowIndex) => (
                <TableRow
                  key={`skeleton-${rowIndex}`}
                  className="hover:bg-transparent"
                >
                  {Array.from({ length: columnCount }, (_, cellIndex) => (
                    <TableCell key={cellIndex} className="px-3 py-2.5">
                      <Skeleton className="h-4 w-full max-w-32" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : rows.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell
                  colSpan={columnCount}
                  className="px-3 py-10 text-center whitespace-normal"
                >
                  <span className="inline-flex flex-col items-center gap-2 text-sm text-muted-foreground">
                    <InboxIcon aria-hidden="true" className="size-5" />
                    {emptyMessage}
                  </span>
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="px-3 py-2.5">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {isLoading ? (
        <span className="sr-only" role="status">
          Cargando datos…
        </span>
      ) : null}
    </div>
  )
}
