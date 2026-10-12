import type { ReactNode } from "react";

export interface PaginaProps {
  ancho?: "angosto" | "medio" | "ancho";
  children: ReactNode;
}

export function Pagina(props: PaginaProps) {
  void props;
  return null;
}

export function TituloPagina(props: { children: ReactNode }) {
  void props;
  return null;
}
