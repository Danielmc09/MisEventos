import type { ReactNode } from "react";

export interface FranjaFechaProps {
  dia: string;
  mes: string;
  gradiente: string;
  children?: ReactNode;
}

export function FranjaFecha({ dia }: FranjaFechaProps) {
  return dia === "" ? null : null;
}
