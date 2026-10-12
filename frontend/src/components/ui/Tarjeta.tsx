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
export function Tarjeta({
  as: Etiqueta = "article",
  indice,
  cabecera,
  children,
  ...props
}: TarjetaProps) {
  const animada = indice !== undefined;
  const estilos = `relative rounded-lg bg-panel shadow-tarjeta ${
    animada ? "motion-safe:animate-entrar motion-safe:[animation-delay:calc(var(--i)*60ms)]" : ""
  }`;
  const cuerpo = "flex flex-col gap-4 p-4 md:p-6";
  return (
    <Etiqueta
      {...props}
      style={animada ? ({ "--i": Math.min(indice, MAXIMO_ESCALON) } as CSSProperties) : undefined}
      className={cabecera ? `flex flex-col overflow-hidden ${estilos}` : `${cuerpo} ${estilos}`}
    >
      {cabecera ? (
        <>
          {cabecera}
          <div className={`grow ${cuerpo}`}>{children}</div>
        </>
      ) : (
        children
      )}
    </Etiqueta>
  );
}
