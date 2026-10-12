import type { ReactNode } from "react";

export interface TarjetaProps {
  as?: "article" | "li" | "div" | "section";
  /** Posición en una lista, para escalonar la entrada. */
  indice?: number;
  children: ReactNode;
}

export function Tarjeta(props: TarjetaProps) {
  void props;
  return null;
}
