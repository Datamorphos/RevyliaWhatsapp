/**
 * Contenedor de las pantallas de acceso (`/login`, `/sin-acceso`).
 * Centra el contenido y no depende del shell del panel.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-svh w-full items-center justify-center bg-muted/30 p-6">
      <div className="w-full max-w-sm">{children}</div>
    </main>
  );
}
