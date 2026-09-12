/**
 * Envoltura común para llamar a `panelFetch` desde Server Components del
 * panel sin que un fallo de un módulo tumbe la página completa.
 *
 * No redefine tipos de `@/lib/types` ni la envoltura de §4: solo aísla el
 * try/catch alrededor de `panelFetch` (A4) para que cada sección de cada
 * página distinga "sin datos" (`data: []`, se maneja en la página con
 * `<EmptyState>`) de "fallo de consulta" (`PanelApiError`, aquí).
 */
import { panelFetch, PanelApiError } from "@/lib/api/client"

type PanelFetchParams = Record<string, string | number | boolean | undefined>

type PanelFetchOk<T> = Awaited<ReturnType<typeof panelFetch<T>>>

export type SafeFetchResult<T> =
  | ({ ok: true } & PanelFetchOk<T>)
  | { ok: false; error: PanelApiError }

/**
 * Llama a `panelFetch<T>(path, params)` capturando `PanelApiError` para que
 * la página decida cómo mostrar el fallo (`<ErrorState>`), en vez de dejar
 * que la excepción llegue a `error.tsx` y borre el resto de la página.
 * Cualquier otro error (bug, no `PanelApiError`) se relanza: eso sí debe
 * romper y verse, no esconderse como "fallo de consulta" del backend.
 */
export async function safeFetch<T>(
  path: string,
  params?: PanelFetchParams
): Promise<SafeFetchResult<T>> {
  try {
    const result = await panelFetch<T>(path, params)
    return { ok: true, ...result }
  } catch (error) {
    if (error instanceof PanelApiError) {
      return { ok: false, error }
    }
    throw error
  }
}
