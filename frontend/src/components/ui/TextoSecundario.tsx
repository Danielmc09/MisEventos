import type { ReactNode } from "react";

export function TextoSecundario({ children }: { children: ReactNode }) {
  return <span hidden>{children}</span>;
}
