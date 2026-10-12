import type { ComponentProps, ReactNode } from "react";

export interface BotonIconoProps extends Omit<ComponentProps<"button">, "children" | "aria-label"> {
  etiqueta: string;
  texto: string;
  icono: ReactNode;
  variante?: "neutro" | "peligro";
}

// Esqueleto provisional.
export function BotonIcono(props: BotonIconoProps) {
  void props;
  return <div />;
}
