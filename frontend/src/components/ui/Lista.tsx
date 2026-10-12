import type { ReactNode } from "react";

/** Una lista con nombre accesible; los hijos son `<li>`. */
export function Lista({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <ul aria-label={etiqueta} className="flex flex-col gap-2 text-sm text-gray-700">
      {children}
    </ul>
  );
}
