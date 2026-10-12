import type { ReactNode } from "react";

const ANCHOS = {
  angosto: "max-w-md",
  medio: "max-w-3xl",
  ancho: "max-w-6xl",
} as const;

export interface PaginaProps {
  ancho?: keyof typeof ANCHOS;
  children: ReactNode;
}

/** El contenedor de cada pantalla: ancho máximo, aire alrededor y 24 px entre bloques. */
export function Pagina({ ancho = "medio", children }: PaginaProps) {
  return (
    <main className={`mx-auto flex w-full flex-col gap-6 p-4 md:p-6 ${ANCHOS[ancho]}`}>
      {children}
    </main>
  );
}

export function TituloPagina({ children }: { children: ReactNode }) {
  return <h1 className="text-2xl font-bold break-words text-tinta">{children}</h1>;
}
