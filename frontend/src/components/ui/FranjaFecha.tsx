import type { ReactNode } from "react";

export interface FranjaFechaProps {
  dia: string;
  mes: string;
  /** Las clases del gradiente de fondo (de `claseGradiente`). */
  gradiente: string;
  /** Lo que va a la derecha de la fecha, p. ej. el estado. */
  children?: ReactNode;
}

/** Franja de color con la fecha en un bloque claro: el texto va sobre `panel`, no sobre el degradé. */
export function FranjaFecha({ dia, mes, gradiente, children }: FranjaFechaProps) {
  return (
    <div className={`flex items-start justify-between gap-3 p-4 md:px-6 ${gradiente}`}>
      <div
        aria-hidden="true"
        className="flex w-14 flex-col items-center rounded-lg bg-panel py-2 text-tinta shadow-tarjeta"
      >
        <span className="text-2xl/none font-bold">{dia}</span>
        <span className="text-sm font-semibold">{mes}</span>
      </div>
      <div>{children}</div>
    </div>
  );
}
