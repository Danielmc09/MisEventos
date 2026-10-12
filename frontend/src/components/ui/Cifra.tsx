import type { ReactNode } from "react";

/** Un dato destacado con su etiqueta; va dentro de un `<dl>`. */
export function Cifra({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-texto-suave">{etiqueta}</dt>
      <dd className="text-2xl font-bold text-tinta">{children}</dd>
    </div>
  );
}
