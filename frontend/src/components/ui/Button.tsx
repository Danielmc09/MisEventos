import type { ComponentProps } from "react";
import {
  ANCHO_BOTON,
  BASE_BOTON,
  VARIANTES_BOTON,
  type AnchoBoton,
  type VarianteBoton,
} from "./estilosBoton";
import { Spinner } from "./Spinner";

export interface ButtonProps extends ComponentProps<"button"> {
  loading?: boolean;
  variante?: VarianteBoton;
  ancho?: AnchoBoton;
}

export function Button({
  loading = false,
  variante = "primario",
  ancho,
  disabled,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      // Con el spinner a la izquierda, un poco menos de padding de ese lado.
      className={`${BASE_BOTON} ${loading ? "pr-4 pl-3" : "px-4"} ${VARIANTES_BOTON[variante]} ${ancho ? ANCHO_BOTON[ancho] : ""} ${className}`}
    >
      {loading && <Spinner heredar className="h-4 w-4" />}
      {children}
    </button>
  );
}
