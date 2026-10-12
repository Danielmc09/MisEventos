import type { ReactNode } from "react";

export interface PestanasProps {
  etiqueta: string;
  pestanas: { id: string; titulo: string }[];
  activa: string;
  onCambiar: (id: string) => void;
  children: ReactNode;
}

export function Pestanas(props: PestanasProps) {
  void props;
  return null;
}
