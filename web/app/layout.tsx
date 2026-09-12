import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { ThemeProvider } from "@/components/shell/theme-provider";
import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

// `app/globals.css` mapea `--font-sans` en `@theme inline`, así que la variable
// de next/font tiene que llamarse exactamente así para que `font-sans` resuelva.
const fontSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const fontMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Panel Revylia",
    template: "%s · Panel Revylia",
  },
  description:
    "Panel interno de consulta de la clínica: agenda, pacientes, oportunidades, escalaciones, recuperación y eventos de WhatsApp.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
};

// El layout raíz NO monta el shell del panel: `web/app/(auth)/**` (inicio de
// sesión) también cuelga de aquí y no debe renderizarse dentro del sidebar.
// `<AppShell>` se monta en el layout del grupo `(panel)`.
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      suppressHydrationWarning
      className={`${fontSans.variable} ${fontMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <ThemeProvider>
          {children}
          <Toaster position="bottom-right" closeButton richColors />
        </ThemeProvider>
      </body>
    </html>
  );
}
