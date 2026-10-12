import type { ReactNode } from "react";

export interface ItemMenu {
  texto: string;
  onSelect?: () => void;
  to?: string;
  peligro?: boolean;
}

export interface MenuAccionesProps {
  etiqueta: string;
  items: ItemMenu[];
  variante?: "boton" | "circulo";
  alinear?: "inicio" | "fin";
  deshabilitado?: boolean;
  children: ReactNode;
}

// Esqueleto provisional: el comportamiento llega con el commit de implementación.
export function MenuAcciones(props: MenuAccionesProps) {
  void props;
  return <div />;
}
