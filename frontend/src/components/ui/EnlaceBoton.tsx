import type { ReactNode } from "react";

export interface EnlaceBotonProps {
  to: string;
  children: ReactNode;
}

export function EnlaceBoton({ to }: EnlaceBotonProps) {
  void to;
  return null;
}
