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

/**
 * Ancho máximo de una celda antes de recortar con "…".
 *
 * Sin este tope, una sola columna de texto libre decide el ancho de toda la
 * tabla: en Eventos, "Respuesta" (80 caracteres) medía 550 px y empujaba la
 * tabla a 1362 px dentro de un contenedor de 1119 px, dejando dos columnas
 * fuera de la vista. Con 18rem la tabla de Eventos entra justa a 1440 px.
 *
 * `max-width` en un `<td>` de una tabla `auto` solo acota el ancho *preferido*:
 * si la tabla ya cabe, el navegador reparte el sobrante y el tope no recorta
 * nada; y nunca lleva una columna por debajo de su ancho mínimo de contenido.
 * Es decir, solo actúa cuando de verdad sobra ancho. Las columnas que se miden
 * por debajo del tope (paciente, fechas, estados) quedan intactas, y las celdas
 * apiladas (nombre + teléfono) nunca se recortan: medido en Pacientes,
 * Oportunidades y Escalaciones a 1440, 1000 y 390 px.
 */
const CELL_MAX_WIDTH = "max-w-72"

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

  const wrapperRef = React.useRef<HTMLDivElement>(null)
  const [hasHiddenColumns, setHasHiddenColumns] = React.useState(false)

  /**
   * A 390 px una tabla de seis columnas enseña dos, y nada indica que las otras
   * cuatro existan. Se observa el desbordamiento real del contenedor para
   * pintar un degradado en el borde derecho y una línea de ayuda en móvil, que
   * desaparecen al llegar al final del desplazamiento.
   *
   * El contenedor que hace scroll lo crea `<Table>` (shadcn), no este
   * componente, así que se busca por su `data-slot` — el atributo estable con
   * el que shadcn identifica sus partes — en vez de duplicar el contenedor.
   */
  React.useEffect(() => {
    const scroller = wrapperRef.current?.querySelector<HTMLElement>(
      '[data-slot="table-container"]'
    )
    if (!scroller) return

    const update = () => {
      const remaining =
        scroller.scrollWidth - scroller.clientWidth - scroller.scrollLeft
      setHasHiddenColumns(remaining > 1)
    }

    update()
    scroller.addEventListener("scroll", update, { passive: true })
    const observer = new ResizeObserver(update)
    observer.observe(scroller)
    if (scroller.firstElementChild) observer.observe(scroller.firstElementChild)

    return () => {
      scroller.removeEventListener("scroll", update)
      observer.disconnect()
    }
  }, [data, columns])

  const headerGroups = table.getHeaderGroups()
  const rows = table.getRowModel().rows
  const columnCount =
    headerGroups[headerGroups.length - 1]?.headers.length ?? columns.length

  return (
    <div
      ref={wrapperRef}
      aria-busy={isLoading}
      className={cn(
        "relative rounded-xl border border-border bg-card",
        className
      )}
    >
      <div className="relative overflow-hidden rounded-xl">
        {hasHiddenColumns ? (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 right-0 z-10 w-10 bg-gradient-to-l from-card to-transparent"
          />
        ) : null}
        <Table>
          <TableHeader>
            {headerGroups.map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent">
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className="bg-muted px-3 text-xs font-medium text-muted-foreground first:rounded-tl-xl last:rounded-tr-xl"
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
                    <TableCell
                      key={cell.id}
                      className={cn(
                        "overflow-hidden px-3 py-2.5 text-ellipsis",
                        CELL_MAX_WIDTH
                      )}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {hasHiddenColumns ? (
        <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground md:hidden">
          Desliza la tabla para ver el resto de columnas.
        </p>
      ) : null}

      {isLoading ? (
        <span className="sr-only" role="status">
          Cargando datos…
        </span>
      ) : null}
    </div>
  )
}
