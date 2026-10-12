import type { ReactNode } from "react";

/** Un valor que se lee carácter por carácter o se copia (una contraseña, un código): monoespaciado y seleccionable de un clic. */
export function Monoespaciado({ children }: { children: ReactNode }) {
  return (
    <code className="block rounded-md bg-fondo px-3 py-2 font-mono text-lg break-all text-tinta select-all">
      {children}
    </code>
  );
}
