import type { ComponentProps } from "react";
import { BASE_BOTON, VARIANTES_BOTON, type VarianteBoton } from "./estilosBoton";
import { Spinner } from "./Spinner";

export interface ButtonProps extends ComponentProps<"button"> {
  loading?: boolean;
  variante?: VarianteBoton;
}

export function Button({
  loading = false,
  variante = "primario",
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
      className={`${BASE_BOTON} ${loading ? "pr-4 pl-3" : "px-4"} ${VARIANTES_BOTON[variante]} ${className}`}
    >
      {loading && <Spinner heredar className="h-4 w-4" />}
      {children}
    </button>
  );
}
