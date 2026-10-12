import type { ComponentProps, ReactNode } from "react";

/** Un formulario: los campos de un bloque van juntos (8 px) y los bloques, separados (24 px). */
export function Formulario({ className = "", children, ...props }: ComponentProps<"form">) {
  return (
    <form {...props} className={`flex flex-col gap-6 ${className}`}>
      {children}
    </form>
  );
}

export function GrupoCampos({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-2">{children}</div>;
}
