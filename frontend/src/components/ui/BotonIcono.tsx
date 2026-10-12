import type { ComponentProps, ReactNode } from "react";
import { Tooltip } from "./Tooltip";

const VARIANTES = {
  neutro: "text-tinta hover:bg-fondo",
  peligro: "text-error hover:bg-error-suave",
  secundario: "bg-acento-suave text-tinta hover:brightness-95",
} as const;

export interface BotonIconoProps extends Omit<ComponentProps<"button">, "children" | "aria-label"> {
  /** Qué hace y sobre qué: «Eliminar la sesión «Apertura»». Es el nombre accesible. */
  etiqueta: string;
  /** El texto corto: lo dice el tooltip y, en pantallas angostas, se ve junto al ícono. */
  texto: string;
  icono: ReactNode;
  variante?: keyof typeof VARIANTES;
  /** El texto solo lo dice el tooltip, también en angosto: el botón queda cuadrado. */
  soloIcono?: boolean;
}

/** Acción secundaria que se repite por fila: ícono con tooltip (en angosto, ícono + texto corto). */
export function BotonIcono({
  etiqueta,
  texto,
  icono,
  variante = "neutro",
  soloIcono,
  type = "button",
  ...props
}: BotonIconoProps) {
  return (
    <Tooltip texto={texto}>
      <button
        {...props}
        type={type}
        aria-label={etiqueta}
        className={`inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-md px-2 font-semibold focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-foco disabled:cursor-not-allowed disabled:opacity-60 md:min-h-10 md:min-w-10 motion-safe:transition-[background-color,transform] motion-safe:duration-100 not-disabled:motion-safe:active:scale-97 ${VARIANTES[variante]}`}
      >
        {icono}
        {!soloIcono && (
          <span aria-hidden="true" className="md:hidden">
            {texto}
          </span>
        )}
      </button>
    </Tooltip>
  );
}
