import type { ReactNode } from "react";

export interface TablaProps {
  descripcion: string;
  columnas: string[];
  filas: { id: string; celdas: ReactNode[] }[];
}

export function Tabla(props: TablaProps) {
  void props;
  return null;
}
