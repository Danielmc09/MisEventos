import type { CSSProperties, HTMLAttributes, ReactNode } from "react";

/** Cuántas tarjetas se escalonan antes de entrar todas juntas: un grupo chico. */
const MAXIMO_ESCALON = 5;

export interface TarjetaProps extends HTMLAttributes<HTMLElement> {
  as?: "article" | "li" | "div" | "section";
  /** Posición en una lista, para escalonar la entrada. Sin índice, no se anima. */
  indice?: number;
  /** Una franja a todo el ancho, arriba del contenido. */
  cabecera?: ReactNode;
  children: ReactNode;
}

/** Superficie con sombra en capas, sin borde. Sus hijos directos se separan 16 px: un hijo por grupo. */
export function Tarjeta({ as: Etiqueta = "article", indice, children, ...props }: TarjetaProps) {
  const animada = indice !== undefined;
  return (
    <Etiqueta
      {...props}
      style={animada ? ({ "--i": Math.min(indice, MAXIMO_ESCALON) } as CSSProperties) : undefined}
      className={`flex flex-col gap-4 rounded-lg bg-panel p-4 shadow-tarjeta md:p-6 ${
        animada
          ? "motion-safe:animate-entrar motion-safe:[animation-delay:calc(var(--i)*60ms)]"
          : ""
      }`}
    >
      {children}
    </Etiqueta>
  );
}
