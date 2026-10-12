import type { ReactNode } from "react";

export function TituloSeccion({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <h2 id={id} className="text-xl font-semibold">
      {children}
    </h2>
  );
}
