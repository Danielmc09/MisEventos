import type { ReactNode } from "react";

export interface ListaDatosProps {
  datos: { etiqueta: string; valor: ReactNode }[];
}

export function ListaDatos(props: ListaDatosProps) {
  void props;
  return null;
}
