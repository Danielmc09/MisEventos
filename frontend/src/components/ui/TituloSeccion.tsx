import type { ReactNode } from "react";

export function TituloSeccion({ id }: { id?: string; children: ReactNode }) {
  return <div id={id} />;
}
