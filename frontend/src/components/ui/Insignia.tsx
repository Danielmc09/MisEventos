import type { ReactNode } from "react";

export interface InsigniaProps {
  tono?: "exito" | "neutro";
  children: ReactNode;
}

export function Insignia({ children }: InsigniaProps) {
  void children;
  return null;
}
