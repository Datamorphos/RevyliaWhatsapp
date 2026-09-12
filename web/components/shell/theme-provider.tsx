"use client"

import * as React from "react"
import { ThemeProvider as NextThemesProvider } from "next-themes"

/**
 * Envoltura de cliente para `next-themes`.
 *
 * `attribute="class"` es obligatorio: `app/globals.css` declara
 * `@custom-variant dark (&:is(.dark *))` y define la paleta oscura bajo `.dark`,
 * así que el tema tiene que escribirse como clase en `<html>`, no como
 * `data-theme`. Se pasa explícito para no depender del valor por omisión.
 */
export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  )
}
