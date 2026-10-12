import type { ReactNode } from "react";

export interface ListaProps {
  etiqueta: string;
  /** `anidada`: con sangría y una línea de acento, para lo que cuelga de otra cosa (una tarjeta). */
  anidada?: boolean;
  children: ReactNode;
}

/** Una lista con nombre accesible; los hijos son `<li>`. */
export function Lista({ etiqueta, anidada = false, children }: ListaProps) {
  return (
    <ul
      aria-label={etiqueta}
      className={`flex flex-col gap-2 text-sm text-texto-suave ${
        anidada ? "border-l-2 border-acento-decorativo pl-4" : ""
      }`}
    >
      {children}
    </ul>
  );
}
