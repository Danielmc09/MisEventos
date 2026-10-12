import type { ReactNode } from "react";

const ESTILOS = {
  seccion: "text-xl font-bold text-tinta",
  tarjeta: "text-lg font-bold text-tinta",
  grupo: "font-semibold text-texto-suave",
  elemento: "font-bold text-tinta",
} as const;

export interface TituloSeccionProps {
  id?: string;
  /** El nivel del encabezado: 2 por defecto. */
  nivel?: 2 | 3 | 4;
  estilo?: keyof typeof ESTILOS;
  children: ReactNode;
}

export function TituloSeccion({ id, nivel = 2, estilo = "seccion", children }: TituloSeccionProps) {
  const Etiqueta = `h${nivel}` as const;
  return (
    <Etiqueta id={id} className={`break-words ${ESTILOS[estilo]}`}>
      {children}
    </Etiqueta>
  );
}
