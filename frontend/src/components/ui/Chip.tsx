import type { ReactNode } from "react";

export interface ChipProps {
  tono?: "neutro" | "exito" | "error" | "advertencia" | "finalizado" | "acento";
  /** Si viene, el chip se puede quitar con un botón. */
  onQuitar?: () => void;
  etiquetaQuitar?: string;
  children: ReactNode;
}

export function Chip(props: ChipProps) {
  void props;
  return null;
}
