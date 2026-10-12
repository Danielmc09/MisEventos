import type { ReactNode } from "react";

export function Cifra({ etiqueta }: { etiqueta: string; children: ReactNode }) {
  return <div title={etiqueta} />;
}
