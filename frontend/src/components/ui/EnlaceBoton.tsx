import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ANCHO_BOTON,
  BASE_BOTON,
  VARIANTES_BOTON,
  type AnchoBoton,
  type VarianteBoton,
} from "./estilosBoton";

export interface EnlaceBotonProps {
  to: string;
  variante?: VarianteBoton;
  ancho?: AnchoBoton;
  children: ReactNode;
}

/** Navega a otra pantalla, pero con el aspecto de un botón. */
export function EnlaceBoton({ to, variante = "primario", ancho, children }: EnlaceBotonProps) {
  return (
    <Link
      to={to}
      className={`${BASE_BOTON} px-4 ${VARIANTES_BOTON[variante]} ${ancho ? ANCHO_BOTON[ancho] : ""}`}
    >
      {children}
    </Link>
  );
}
