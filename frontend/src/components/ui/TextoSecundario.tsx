import type { ReactNode } from "react";

export function TextoSecundario({
  pequeno = false,
  id,
  children,
}: {
  pequeno?: boolean;
  id?: string;
  children: ReactNode;
}) {
  return (
    <p id={id} className={`break-words text-texto-suave ${pequeno ? "text-sm" : ""}`}>
      {children}
    </p>
  );
}
