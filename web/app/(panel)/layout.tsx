import type { ReactNode } from "react"

import { AppShell } from "@/components/shell/app-shell"
import { CopilotProvider } from "@/components/copilot/copilot-provider"
import { RevyliaCopilotSidebar } from "@/components/copilot/copilot-sidebar"

export default function PanelLayout({ children }: { children: ReactNode }) {
  return (
    <CopilotProvider>
      <AppShell>{children}</AppShell>
      <RevyliaCopilotSidebar />
    </CopilotProvider>
  )
}
