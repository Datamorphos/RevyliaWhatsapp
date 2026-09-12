# Sistema de diseño del panel Revylia

Documento de decisión. Explica **qué sistema de diseño open source usa `web/`,
por qué se eligió ese y no otro**, qué se tomó literalmente del ecosistema, qué
hubo que escribir a mano, y cómo se usan los componentes propios.

Ámbito: el panel interno de consulta (`web/app/(panel)/**`). No aplica al
backend (`src/**`).

---

## 1. El caso concreto

Antes de comparar nada, los requisitos reales de **este** panel, porque son los
que deciden:

| # | Requisito | Consecuencia para la elección |
|---|-----------|-------------------------------|
| R1 | Panel clínico interno, **denso en datos**: seis listados tabulares y un tablero de 13 indicadores. | Necesita tablas y tarjetas sobrias, no un kit de marketing. |
| R2 | **Solo lectura**. El panel no crea, edita ni envía nada. | Casi no hay formularios. Un kit con 60 controles de entrada es peso muerto. |
| R3 | **Todo el texto en español**, incluidos estados, fechas y números. | Los textos y formatos no pueden venir enlatados en inglés dentro del componente. |
| R4 | **Mínimo código propio**. El equipo es pequeño y el panel es una pieza de un producto mayor. | Hay que copiar, no reinventar. |
| R5 | **Licencia permisiva** y sin dependencia de un proveedor comercial. | Descarta cualquier cosa cuyo valor real esté detrás de una licencia de pago. |
| R6 | Stack ya fijado: **Next.js 16.3.5 (App Router, RSC), React 19.2.8, Tailwind CSS v4**. | El kit debe funcionar con Server Components y con Tailwind v4 sin capa de compatibilidad. |
| R7 | Tema **claro y oscuro** obligatorios (el panel se usa en consultorio y en recepción). | Hace falta un sistema de tokens, no colores sueltos. |

---

## 2. Comparación de alternativas

Todas son proyectos open source reales y vigentes. Licencias y repositorios
verificados contra la API de GitHub y contra el `package.json` instalado en
`web/node_modules/`, no de memoria.

| Opción | Repositorio | Licencia | Modelo | Por qué sí / por qué no aquí |
|--------|-------------|----------|--------|------------------------------|
| **shadcn/ui** ✅ | https://github.com/shadcn-ui/ui | **MIT** | Copias el código fuente del componente a tu repo (no es una dependencia npm). | **Elegido.** Ver §3. |
| Tremor | https://github.com/tremorlabs/tremor | **Apache-2.0** | Copy & paste, igual que shadcn. Enfocado a dashboards y gráficas. | Lo más cercano al caso de uso: nace para paneles. Pero su fuerza son las **gráficas**, y aquí el 90 % del panel son **tablas y cifras deterministas**; además al ser adquirido por Vercel convergió hacia el mismo terreno que shadcn. Aportaba menos de lo que costaba mantener dos vocabularios de tokens. |
| Mantine | https://github.com/mantinedev/mantine | **MIT** | Librería npm con estilos propios (CSS Modules). | Muy completa y con buenos hooks. Pero trae su **propio motor de estilos**, que convive mal con Tailwind v4 ya instalado, y su `MantineProvider` empuja a componentes de cliente: choca con R6 (RSC). |
| Ant Design | https://github.com/ant-design/ant-design | **MIT** | Librería npm, sistema de diseño cerrado y muy opinado. | Su `Table` resuelve sola casi todo lo de R1, y trae i18n de fábrica (R3). Pero impone una identidad visual entera, pesa mucho, y **personalizarla significa pelear con su motor de temas**. Contradice R4 al revés: escribes poco, pero lo poco que escribes es difícil. |
| Park UI | https://github.com/chakra-ui/park-ui | **MIT** | Copy & paste sobre Ark UI + Panda CSS. | Buena accesibilidad y multi-framework. Pero exige **Panda CSS**, otro motor de estilos, con el mismo problema que Mantine frente a R6. Comunidad bastante menor. |
| Material UI (MUI Core) | https://github.com/mui/material-ui | **MIT** | Librería npm, Material Design. | Core es MIT y gratuito, pero **lo que este panel necesitaría de verdad —el Data Grid con filtros y agrupación— vive en MUI X Pro/Premium, que son licencias comerciales de pago** ([licenciamiento de MUI X](https://mui.com/x/introduction/licensing/)). Elegir MUI es aceptar que la funcionalidad tabular crece hacia una factura. Choca frontalmente con R5. |

> Nota sobre el mito de "todo es MIT": no lo es. **Tremor es Apache-2.0** (igual
> de permisiva, pero con cláusula de patentes y requisito de NOTICE), y **MUI
> tiene un tramo comercial**. Conviene decirlo explícitamente antes de que
> alguien lo descubra en una auditoría.
>
> Contexto útil sobre Tremor: fue adquirido por Vercel en enero de 2025 y todo
> el producto pasó a ser libre, incluidos los *Blocks* que antes eran de pago.
> Lo verificado contra la API de GitHub es la licencia del repositorio principal
> (**Apache-2.0**); la de los *Blocks* solo está declarada en su web, así que si
> se fueran a usar conviene comprobarla en el repositorio correspondiente.

---

## 3. Por qué shadcn/ui para este caso

Tres razones, en orden de peso:

**3.1. El código es nuestro desde el día uno (R3, R4).**
shadcn/ui no es una dependencia: el CLI **copia el `.tsx` a `web/components/ui/`**
y ahí se queda. Eso resuelve R3 de la forma más barata posible — cuando hace
falta que un componente diga "Solo lectura" o formatee una fecha en
`America/Bogota`, se edita el archivo, no se pelea con una API de traducción.
Y resuelve R4 sin caer en la trampa opuesta: se escribe poco porque **se copia
mucho**, pero lo copiado es legible y modificable.

**3.2. Tokens CSS + Tailwind v4, que es exactamente el stack ya instalado (R6, R7).**
El tema vive en variables CSS en `web/app/globals.css` y se expone a Tailwind
con `@theme inline`. No hay segundo motor de estilos, no hay proveedor de tema
obligatorio en el árbol de React, y los componentes son compatibles con Server
Components salvo los que necesitan estado (marcados con `"use client"`).
Mantine y Park UI habrían añadido un motor de estilos paralelo.

**3.3. Licencia MIT limpia y sin tramo comercial (R5).**
No hay componente que se quede fuera por no pagar. La comparación con MUI es
la que decide: el `Table` de shadcn es headless y gratis para siempre; el
Data Grid equivalente de MUI no.

**Lo que se pierde y se asume conscientemente:** shadcn no da tabla con
ordenación/filtrado/paginación "de caja". Aquí no es pérdida — el contrato del
panel exige que **ordenar y paginar los haga el servidor** para que la lectura
no sea falsa (ver `docs/CONTRACT_PANEL.md`), así que una tabla que ordena en
cliente habría sido un problema, no una ventaja.

### Configuración exacta elegida

`web/components.json`:

| Ajuste | Valor | Por qué |
|--------|-------|---------|
| `style` | `base-nova` | Estilo sobre **Base UI** (`@base-ui/react`, MIT, de los creadores de Radix y Material UI). Primitivas accesibles, sin estilos. |
| `tailwind.baseColor` | `neutral` | Panel clínico: la escala de grises no compite con los colores semánticos (rojo = fallido, ámbar = pendiente). El color solo aparece cuando significa algo. |
| `tailwind.cssVariables` | `true` | Requisito para tener claro/oscuro con un solo juego de clases. |
| `iconLibrary` | `lucide` | Trazo fino y uniforme, bien a 16 px, que es el tamaño real del panel. |
| `rsc` | `true` | Marca `"use client"` solo donde hace falta. |

---

## 4. Qué se tomó literalmente y qué hubo que escribir

### 4.1. Tomado literalmente del ecosistema open source

**25 componentes en `web/components/ui/`**, copiados sin modificar la lógica:

```
alert  avatar  badge  breadcrumb  button  card  chart  command  dialog
dropdown-menu  input-group  input  label  popover  scroll-area  select
separator  sheet  sidebar  skeleton  sonner  table  tabs  textarea  tooltip
```

Los tres que más trabajo ahorraron:

- **`sidebar.tsx`** — resuelve solo el armazón entero: colapso a iconos con
  tooltip, atajo `Ctrl/⌘ + B`, rail arrastrable, persistencia en cookie y —lo
  importante— **conmutación automática a `Sheet` por debajo de 768 px**.
  Reimplementar eso a mano habrían sido cientos de líneas y varios bugs.
- **`chart.tsx`** — envoltura de Recharts que ya lee `--chart-1..5` y pinta
  tooltip y leyenda con los tokens del tema, en claro y en oscuro.
- **`table.tsx` + `@tanstack/react-table`** — marcado accesible y modelo de
  columnas headless.

Dependencias de ese ecosistema, con licencia verificada en `node_modules`:

| Paquete | Versión | Licencia |
|---------|---------|----------|
| `@base-ui/react` | 1.8.0 | MIT |
| `@tanstack/react-table` | 8.21.3 | MIT |
| `recharts` | 3.8.0 | MIT |
| `lucide-react` | 1.45.0 | **ISC** |
| `class-variance-authority` | 0.7.1 | **Apache-2.0** |
| `next-themes` | 0.4.6 | MIT |
| `sonner` | 2.0.8 | MIT |
| `cmdk` | 1.1.1 | MIT |
| `tailwindcss` | 4.3.3 | MIT |
| `tw-animate-css` | 1.4.0 | MIT |

Todas permisivas y compatibles con uso interno y comercial. Ninguna es copyleft.

> `@tanstack/react-table` está fijado en **v8 a propósito**. v9 cambia el
> constraint de `RowData` y la forma de renderizar celdas; la API v8 es la de
> los ejemplos de shadcn y no compensaba pelear la migración. Cualquier columna
> nueva debe escribirse con la API v8.

### 4.2. Escrito a mano, y por qué

Nada de lo siguiente existe en shadcn/ui. Son la capa de **dominio**, no de UI:

| Componente | Por qué no se pudo copiar |
|------------|---------------------------|
| `data/status-badge.tsx` | Traduce los valores de `revylia.*` (`pending`, `urgent`, `failed`…) a español y a un tono. Es vocabulario del esquema SQL de la clínica: no existe fuera de este proyecto. |
| `data/query-meta.tsx` | Requisito de producto: cada cifra debe poder contrastarse contra su consulta (fuente, filtros, momento, total). Es la envoltura `meta` de la API, no un patrón genérico. |
| `data/kpi-card.tsx` | Tarjeta de indicador con tono semántico y **fórmula visible**. Es una composición fina sobre `ui/card.tsx`, no una reimplementación. |
| `data/data-table.tsx` | Cableado de `@tanstack/react-table` v8 con `ui/table.tsx`, más las reglas propias: sin ordenación de cliente, esqueleto de carga, tope de ancho de celda. |
| `data/empty-state.tsx` y `data/error-state.tsx` | El contrato exige **no confundir "no hay datos" con "no pudimos leerlos"**. Son dos componentes distintos a propósito, con tres señales distintas (color, icono, acción). |
| `shell/app-shell.tsx` | Los siete módulos, su orden y sus textos. Composición sobre `ui/sidebar.tsx`. |
| `shell/page-header.tsx` | Garantiza un único `<h1>` por página. |
| `shell/theme-provider.tsx` / `theme-toggle.tsx` | Envoltura mínima de `next-themes` con `attribute="class"`, obligatorio porque la paleta oscura se define bajo `.dark`. |

Criterio general, y regla para el futuro:

> **Si shadcn ya lo resuelve, se usa shadcn.** Solo se escribe a mano lo que
> depende del vocabulario clínico o del contrato de la API.

---

## 5. Tokens del tema

Se definen en `web/app/globals.css`, tres bloques:

1. `@theme inline` — mapea cada variable a una utilidad de Tailwind
   (`--color-success: var(--success)` habilita `bg-success`, `text-success`, …).
2. `:root` — valores del **tema claro**.
3. `.dark` — valores del **tema oscuro**.

Todos los colores están en `oklch()` porque permite ajustar la luminosidad sin
que cambie el tono, que es justo lo que hace falta para derivar la pareja
claro/oscuro de un mismo color.

### 5.1. Tokens de shadcn (sin tocar)

`background` · `foreground` · `card` · `card-foreground` · `popover` ·
`popover-foreground` · `primary` · `primary-foreground` · `secondary` ·
`secondary-foreground` · `muted` · `muted-foreground` · `accent` ·
`accent-foreground` · `destructive` · `border` · `input` · `ring` · `radius`
· la familia `sidebar-*`.

### 5.2. Tokens añadidos por el panel

| Token | Claro | Oscuro | Para qué | Contraste sobre el fondo |
|-------|-------|--------|----------|--------------------------|
| `--success` | `oklch(0.52 0.12 152)` | `oklch(0.78 0.15 152)` | Confirmada, Activo, Completado, Aprobado, Resuelta. | 5.2 : 1 / 10.5 : 1 |
| `--warning` | `oklch(0.52 0.11 72)` | `oklch(0.82 0.13 80)` | Pendiente, Procesando, Alta, y cifras que piden atención sin ser un error. | 5.6 : 1 / 11.2 : 1 |
| `--info` | `oklch(0.52 0.13 250)` | `oklch(0.78 0.12 250)` | Estado **intermedio**: prioridad Media, En proceso, Abierta, Borrador. | 5.5 : 1 / 9.9 : 1 |
| `--chart-1` | `oklch(0.55 0.13 250)` | `oklch(0.7 0.14 250)` | Serie 1 de gráficas. |  |
| `--chart-2` | `oklch(0.6 0.1 195)` | `oklch(0.74 0.11 195)` | Serie 2. |  |
| `--chart-3` | `oklch(0.6 0.12 152)` | `oklch(0.76 0.14 152)` | Serie 3. |  |
| `--chart-4` | `oklch(0.68 0.12 72)` | `oklch(0.81 0.13 78)` | Serie 4. |  |
| `--chart-5` | `oklch(0.58 0.16 22)` | `oklch(0.71 0.16 22)` | Serie 5. |  |

Cada uno tiene su `*-foreground` para cuando se usa como fondo sólido.

**Por qué existen `--success` / `--warning` / `--info`:** el tema `neutral` de
shadcn solo trae `destructive`. Sin estos tres, "Confirmada", "Pendiente" y
"Media" se renderizaban todas en gris y **la escala de prioridad de Escalaciones
(Urgente › Alta › Media › Baja) era ilegible de un vistazo** — "Media" y "Baja"
salían idénticas. `--info` comparte el tono 250 con `--chart-1` para que los
estados y las gráficas hablen el mismo idioma cromático.

**Por qué existen `--chart-1..5`:** el tema `neutral` los deja en escala de
grises, lo que es inservible para distinguir series.

**Regla de contraste:** los tres tonos semánticos se usan como **texto** sobre
un fondo al 15 % (`bg-success/15 text-success`), igual que hace shadcn con
`destructive`. Por tanto tienen que superar **4.5 : 1 contra `--background`** en
los dos temas. Los valores de la tabla están medidos, no estimados.

### 5.3. Cómo añadir un token nuevo

Ejemplo real: así se añadió `--info`.

**Paso 1 — declarar el color en los dos temas** (`web/app/globals.css`):

```css
:root {
  --info: oklch(0.52 0.13 250);
  --info-foreground: oklch(0.985 0 0);
}

.dark {
  --info: oklch(0.78 0.12 250);
  --info-foreground: oklch(0.205 0 0);
}
```

Mantener el mismo **tono** (el tercer número) en claro y oscuro y mover solo la
**luminosidad** (el primero): así se lee como el mismo color en ambos temas.
Referencia práctica: `L ≈ 0.52` en claro y `L ≈ 0.78` en oscuro dan ~5 : 1 y
~10 : 1 sobre los fondos del panel.

**Paso 2 — exponerlo a Tailwind** en el bloque `@theme inline` del mismo archivo:

```css
@theme inline {
  --color-info: var(--info);
  --color-info-foreground: var(--info-foreground);
}
```

Desde aquí funcionan `text-info`, `bg-info/15`, `border-info`, etc.

**Paso 3 — verificar el contraste en los dos temas antes de usarlo.** Mínimo
**4.5 : 1** contra `--background` si va a ser texto; **3 : 1** si solo es borde
o fondo decorativo.

**Paso 4 — usarlo a través de un componente, nunca suelto en una página.** Un
token semántico sin un componente que lo aplique se convierte en color
arbitrario en tres sprints. `--info` se usa en un único sitio:
`TONE_CLASS` de `components/data/status-badge.tsx`.

---

## 6. Reglas de uso: `components/shell/**`

Armazón y cabeceras. Todo lo de aquí es estructura de página.

### `AppShell`

```tsx
<AppShell>{children}</AppShell>
```

| Prop | Tipo | Notas |
|------|------|-------|
| `children` | `React.ReactNode` | Contenido de la página. |

- **Se monta una sola vez**, en `web/app/(panel)/layout.tsx`. Nunca dentro de
  una página.
- **No se monta en el layout raíz a propósito**: `web/app/(auth)/**` (inicio de
  sesión) cuelga del mismo layout y no debe renderizarse dentro del sidebar.
- Aporta: barra lateral con los siete módulos, barra superior con el nombre del
  módulo activo, insignia "Solo lectura", conmutador de tema, y el colchón
  inferior que evita que el botón flotante del copiloto tape la última fila.
- La navegación se declara en `NAV_ITEMS` dentro del propio archivo. **Añadir un
  módulo = añadir una entrada ahí**, con `href`, `label`, `icon` y `hint`.

### `PageHeader`

```tsx
<PageHeader
  title="Escalaciones"
  description="Ordenadas por prioridad y luego por fecha, tal como las devuelve la API."
  actions={<Button variant="outline">Exportar</Button>}
/>
```

| Prop | Tipo | Notas |
|------|------|-------|
| `title` | `string` | Se renderiza como el **único `<h1>`** de la página. Obligatorio. |
| `description` | `string?` | Una o dos líneas: qué muestra la página y de dónde sale. |
| `actions` | `ReactNode?` | Controles a la derecha: filtros, selector de fechas, acciones **de lectura**. |
| `className` | `string?` | |

- Va **siempre el primero** dentro de la página, una sola vez.
- `actions` nunca debe contener acciones de escritura: el panel es de consulta.

### `ThemeProvider` / `ThemeToggle`

- `ThemeProvider` se monta una vez en `web/app/layout.tsx`. `attribute="class"`
  es obligatorio: la paleta oscura se define bajo `.dark`.
- `ThemeToggle` ya está dentro de `AppShell`. No hace falta montarlo otra vez.

---

## 7. Reglas de uso: `components/data/**`

Presentación de datos que vienen de la API. Todos asumen la envoltura de
respuesta del contrato (`data` + `meta` + `error`).

### Cuál usar: árbol de decisión

```
¿La consulta falló?            → <ErrorState />
¿Devolvió data: [] (lista)?    → <EmptyState />   (o el emptyMessage de DataTable)
¿Devolvió filas?               → <DataTable />
¿Es una cifra suelta?          → <KpiCard />
¿Es un estado del esquema?     → <StatusBadge />
Y debajo de cualquiera de ellos, siempre → <QueryMeta />
```

### `DataTable`

```tsx
<DataTable
  columns={columns}
  data={result.data}
  emptyMessage="No hay citas para los filtros seleccionados."
/>
```

| Prop | Tipo | Notas |
|------|------|-------|
| `columns` | `Array<PanelColumnDef<TData>>` | API **v8** de TanStack Table. |
| `data` | `TData[]` | Filas ya ordenadas **por el servidor**. |
| `emptyMessage` | `string` | Texto de "sin resultados" dentro de la tabla. Obligatorio, en español y específico. |
| `isLoading` | `boolean?` | Pinta cinco filas de esqueleto y anuncia "Cargando datos…". |
| `className` | `string?` | |

Reglas:

- **No se registra ordenación ni paginación de cliente, a propósito.** La API
  ordena y pagina en el servidor con un orden estable; ordenar en el navegador
  reordenaría solo la página visible y daría una lectura falsa del conjunto.
- **Las celdas tienen un tope de ancho (`max-w-72`) y recortan con "…".** Sin
  él, una sola columna de texto libre decide el ancho de toda la tabla: en
  Eventos, "Respuesta" medía 550 px y empujaba la tabla a 1362 px dentro de un
  contenedor de 1119 px, dejando dos columnas fuera de la vista. El tope solo
  actúa cuando la tabla no cabe; si cabe, no recorta nada.
- Por eso, **toda columna de texto largo debe pasar por `truncate()` de
  `@/lib/format` y llevar `title` con el texto completo**, para que el recorte
  visual tenga siempre una forma de leerse entera.
- El tope **nunca** lleva una columna por debajo de su ancho mínimo de
  contenido, así que las celdas apiladas (nombre + teléfono) no se recortan.
  Medido en Pacientes, Oportunidades y Escalaciones a 1440, 1000 y 390 px.
- Cuando quedan columnas fuera de la vista se pinta un degradado en el borde
  derecho y, en móvil, la línea "Desliza la tabla para ver el resto de
  columnas". Ambos desaparecen al llegar al final.

### `KpiCard`

```tsx
<KpiCard
  label="Escalaciones urgentes pendientes"
  value={kpi.value}
  hint={kpi.formula}
  tone={kpi.value > 0 ? "danger" : "default"}
/>
```

| Prop | Tipo | Notas |
|------|------|-------|
| `label` | `string` | Nombre del indicador, en español. |
| `value` | `ReactNode` | Cifra **ya formateada**: usa `formatNumber` de `@/lib/format`. |
| `hint` | `string?` | Procedencia del dato: fórmula, estados incluidos o periodo. Se renderiza en monoespaciada. |
| `tone` | `"default" \| "success" \| "warning" \| "danger"` | Colorea la cifra y el icono. |
| `icon` | Componente **o** elemento de `lucide-react` | Ambas formas son válidas. |
| `className` | `string?` | |

- El `tone` debe **derivarse del valor**, no fijarse a mano: `danger` solo si de
  verdad hay algo que atender. Una rejilla entera en rojo no informa de nada.
- `value` nunca lleva formato dentro del componente: llega ya formateado.

### `StatusBadge`

```tsx
<StatusBadge status={row.original.priority} kind="escalation" />
```

| Prop | Tipo | Notas |
|------|------|-------|
| `status` | `string \| null \| undefined` | Valor crudo del esquema. Si es nulo se pinta `—`. |
| `kind` | `"appointment" \| "patient" \| "opportunity" \| "escalation" \| "recovery" \| "event"` | Selecciona el diccionario. |
| `className` | `string?` | |

- **Nunca se escribe un estado a mano en una celda.** Un valor desconocido se
  muestra con su texto crudo en tono neutro, nunca vacío.
- `statusLabel(status, kind)` da solo la etiqueta en español, sin renderizar
  nada — útil para `title`, `aria-label` o texto plano.
- `kind="escalation"` cubre **prioridad** (`low|medium|high|urgent`) y también
  los valores de `escalations.status`.
- Añadir un estado = añadir una entrada en `MAPS` de `status-badge.tsx`. No se
  inventan tonos nuevos: los cinco (`neutral`, `info`, `success`, `warning`,
  `danger`) son los que hay.

### `QueryMeta`

```tsx
<QueryMeta meta={result.meta} />
```

| Prop | Tipo | Notas |
|------|------|-------|
| `meta` | `QueryMetaValue` | `source` y `generated_at` obligatorios; `filters`, `limit`, `offset`, `total`, `next_cursor`, `pending_validation` opcionales. |
| `className` | `string?` | |

- **Va en todas las páginas que muestran datos, al final.** Es requisito de
  producto, no adorno: cada cifra debe poder contrastarse contra su consulta.
- El tiempo relativo ("hace 2 minutos") se calcula solo tras el montaje; la hora
  absoluta en `America/Bogota` se renderiza siempre.

### `EmptyState` vs `ErrorState`

**No son intercambiables. Confundirlos es un fallo de producto.**

| | `EmptyState` | `ErrorState` |
|---|---|---|
| Significa | La consulta **funcionó** y devolvió `data: []` | La consulta **falló** (p. ej. `503 upstream_unavailable`) |
| Color | Neutro, borde punteado | `destructive`, fondo teñido |
| Icono | Bandeja vacía | Triángulo de alerta |
| Acción | Ninguna | "Reintentar" si se pasa `onRetry` |
| Semántica | — | `role="alert"`: los lectores de pantalla lo anuncian |

```tsx
<EmptyState title="No hay pacientes"
            description="No se encontraron pacientes para los filtros seleccionados." />

<ErrorState title="No se pudo cargar el resumen"
            description={result.error.message}
            onRetry={() => router.refresh()} />
```

| Prop común | Tipo | Notas |
|------------|------|-------|
| `title` | `string` | Qué no hay / qué falló. Obligatorio. |
| `description` | `string?` | Qué puede hacer quien lo lee / mensaje del error ya legible. |
| `className` | `string?` | |

`EmptyState` acepta además `icon`; `ErrorState` acepta `onRetry` (si se omite,
no se muestra el botón).

> Dentro de una tabla no hace falta `EmptyState`: `DataTable` ya pinta su
> `emptyMessage`. `EmptyState` se usa cuando la lista vacía sustituye a la tabla
> entera.

---

## 8. Reglas transversales

1. **Todo el texto visible, en español.** Incluidos `aria-label`, `title` y los
   textos de estado vacío.
2. **Nunca un color literal.** Siempre un token (`text-success`, no
   `text-green-600`). Si falta un token, se añade siguiendo §5.3.
3. **Claro y oscuro, siempre.** Cualquier componente nuevo se revisa en los dos.
4. **390 px es un ancho de verdad.** Las tablas se desplazan dentro de su
   contenedor, nunca desbordan la página.
5. **Densidad antes que decoración.** Este panel se lee, no se contempla:
   primero jerarquía y legibilidad, después estética.
6. **Ninguna acción de escritura.** El panel es de consulta: nada de botones de
   guardar, enviar o aprobar.

---

## 9. Pendiente / conocido

Fuera del alcance de este documento, anotado para quien sea dueño de esos
archivos:

- **`app/(panel)/eventos/page.tsx`** usa `<Alert variant="destructive">` para
  una nota informativa sobre una limitación del esquema. Se pinta entera en rojo
  y se lee como un error. Debería ser `variant="default"`.
- **Los formularios de filtro** de `eventos` y `pacientes` usan `<select>`,
  `<input>` y `<button>` nativos, con alturas y controles desparejos. Hay
  `ui/select.tsx`, `ui/input.tsx`, `ui/label.tsx` y `ui/button.tsx` instalados
  que ya lo resuelven: es la sustitución con mejor relación coste/beneficio que
  queda pendiente.
- **El Resumen muestra 13 indicadores en una rejilla de 4 columnas**, con una
  tarjeta huérfana en la última fila. Agruparlos por bloque (Pacientes / Agenda
  / Agente) daría jerarquía real. Requiere tocar `KPI_DEFS`.
- **Sin gráfica en el Resumen, a propósito.** `Summary` es un mapa plano
  `clave → {value, formula}` de 13 escalares heterogéneos, sin dimensión
  temporal ni series comparables. Una gráfica sobre eso sería decoración: no
  respondería ninguna pregunta que las tarjetas no respondan ya. Si algún día la
  API expone una serie temporal (citas por día, eventos por hora), `ui/chart.tsx`
  y `recharts` ya están instalados y los tokens `--chart-1..5` ya están medidos.
