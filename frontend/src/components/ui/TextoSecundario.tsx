import type { ReactNode } from "react";

export function TextoSecundario({
  pequeno = false,
  children,
}: {
  pequeno?: boolean;
  children: ReactNode;
}) {
  return <p className={`break-words text-texto-suave ${pequeno ? "text-sm" : ""}`}>{children}</p>;
}
