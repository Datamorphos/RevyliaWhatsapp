"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  CalendarDaysIcon,
  HeartPulseIcon,
  LayoutDashboardIcon,
  LockIcon,
  MessageSquareIcon,
  SirenIcon,
  StethoscopeIcon,
  TargetIcon,
  UsersIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ThemeToggle } from "@/components/shell/theme-toggle"

type NavItem = {
  href: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  /** Se lee en el tooltip del sidebar colapsado y en el título del navegador. */
  hint: string
}

/** Los siete módulos del panel, en orden de uso diario. */
const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Resumen",
    icon: LayoutDashboardIcon,
    hint: "Indicadores operativos del día",
  },
  {
    href: "/agenda",
    label: "Agenda",
    icon: CalendarDaysIcon,
    hint: "Citas y disponibilidad",
  },
  {
    href: "/pacientes",
    label: "Pacientes",
    icon: UsersIcon,
    hint: "Directorio y ficha de paciente",
  },
  {
    href: "/oportunidades",
    label: "Oportunidades",
    icon: TargetIcon,
    hint: "Interés detectado por el agente",
  },
  {
    href: "/escalaciones",
    label: "Escalaciones",
    icon: SirenIcon,
    hint: "Casos derivados a una persona",
  },
  {
    href: "/recuperacion",
    label: "Recuperación",
    icon: HeartPulseIcon,
    hint: "Mensajes para pacientes inactivos",
  },
  {
    href: "/eventos",
    label: "Eventos",
    icon: MessageSquareIcon,
    hint: "Estado de procesamiento de WhatsApp",
  },
]

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/"
  return pathname === href || pathname.startsWith(`${href}/`)
}

export interface AppShellProps {
  children: React.ReactNode
}

/**
 * Armazón del panel: barra lateral con los siete módulos + barra superior.
 *
 * Responsive de verdad, usando el `Sidebar` de shadcn:
 * - Escritorio: `collapsible="icon"`, se contrae a una columna de iconos con
 *   tooltip (atajo ⌘B / Ctrl+B, y el rail se arrastra).
 * - Móvil (<768 px): el mismo árbol se renderiza dentro de un `Sheet`, que se
 *   abre con el botón de la barra superior.
 *
 * No se monta en el layout raíz a propósito: `app/(auth)/**` cuelga del mismo
 * layout y el inicio de sesión no debe renderizarse dentro del panel.
 */
export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname() ?? "/"
  const current = NAV_ITEMS.find((item) => isActive(pathname, item.href))

  return (
    <TooltipProvider>
      <SidebarProvider>
        <Sidebar collapsible="icon">
          <SidebarHeader>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  size="lg"
                  tooltip="Panel Revylia"
                  render={<Link href="/" />}
                >
                  <span className="flex aspect-square size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                    <StethoscopeIcon className="size-4" />
                  </span>
                  <span className="grid min-w-0 flex-1 leading-tight">
                    <span className="truncate font-heading font-semibold">
                      Revylia
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      Panel de consulta
                    </span>
                  </span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarHeader>

          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel>Módulos</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {NAV_ITEMS.map((item) => {
                    const active = isActive(pathname, item.href)
                    const Icon = item.icon
                    return (
                      <SidebarMenuItem key={item.href}>
                        <SidebarMenuButton
                          isActive={active}
                          tooltip={item.label}
                          render={
                            <Link
                              href={item.href}
                              aria-current={active ? "page" : undefined}
                            />
                          }
                        >
                          <Icon />
                          <span>{item.label}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    )
                  })}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>

          <SidebarFooter>
            <p className="px-2 pb-1 text-xs leading-snug text-muted-foreground group-data-[collapsible=icon]:hidden">
              Consulta de solo lectura. El panel no crea, edita ni envía nada.
            </p>
          </SidebarFooter>

          <SidebarRail />
        </Sidebar>

        {/* min-w-0 + overflow-x-hidden: sin esto, una tabla ancha estira el
            inset (es hijo flex) y desborda la página entera, recortando los
            avisos de limitación. Con esto, la tabla scrollea dentro de su
            propio contenedor (`overflow-x-auto` en DataTable). */}
        <SidebarInset className="min-w-0 overflow-x-hidden">
          <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/85 px-3 backdrop-blur-sm md:px-4">
            <SidebarTrigger
              aria-label="Mostrar u ocultar el menú lateral"
              className="-ml-1"
            />
            <Separator
              orientation="vertical"
              className="mr-1 data-vertical:h-4 data-vertical:self-center"
            />
            <div className="min-w-0 flex-1">
              <span className="truncate text-sm font-medium text-foreground">
                {current?.label ?? "Panel Revylia"}
              </span>
            </div>
            <Badge
              variant="outline"
              className="hidden gap-1 text-muted-foreground sm:inline-flex"
              title="Ni la API, ni el agente, ni la credencial SQL pueden escribir."
            >
              <LockIcon aria-hidden="true" />
              Solo lectura
            </Badge>
            <ThemeToggle />
          </header>

          <div className="flex min-w-0 flex-1 flex-col gap-5 p-4 md:gap-6 md:p-6">
            {children}
          </div>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
