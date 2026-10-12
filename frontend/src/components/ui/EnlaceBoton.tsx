import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { BASE_BOTON, VARIANTES_BOTON, type VarianteBoton } from "./estilosBoton";

export interface EnlaceBotonProps {
  to: string;
  variante?: VarianteBoton;
  children: ReactNode;
}

/** Navega a otra pantalla, pero con el aspecto de un botón. */
export function EnlaceBoton({ to, variante = "primario", children }: EnlaceBotonProps) {
  return (
    <Link to={to} className={`${BASE_BOTON} px-4 ${VARIANTES_BOTON[variante]}`}>
      {children}
    </Link>
  );
}
