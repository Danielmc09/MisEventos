import type { ReactNode } from "react";

export function TextoSecundario({ children }: { children: ReactNode }) {
  return <p className="text-gray-600">{children}</p>;
}
