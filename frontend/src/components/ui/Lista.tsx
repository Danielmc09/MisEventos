import type { ReactNode } from "react";

export function Lista({ children }: { etiqueta: string; children: ReactNode }) {
  return <div>{children}</div>;
}
