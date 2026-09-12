"use client"

import * as React from "react"
import { useTheme } from "next-themes"
import { MoonIcon, SunIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

/**
 * Alterna claro/oscuro. Antes del montaje no se sabe qué tema resolvió el script
 * de `next-themes`, así que se renderiza un botón inerte del mismo tamaño: evita
 * el desajuste de hidratación sin que la barra superior salte de ancho.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => setMounted(true), [])

  if (!mounted) {
    return (
      <Button
        variant="ghost"
        size="icon-sm"
        aria-hidden="true"
        disabled
        tabIndex={-1}
      >
        <SunIcon />
      </Button>
    )
  }

  const isDark = resolvedTheme === "dark"

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={isDark ? "Usar tema claro" : "Usar tema oscuro"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
    </Button>
  )
}
