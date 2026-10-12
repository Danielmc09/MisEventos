import type { ReactNode } from "react";

const TONOS = {
  neutro: "bg-info-suave text-info",
  exito: "bg-exito-suave text-exito",
  error: "bg-error-suave text-error",
  advertencia: "bg-advertencia-suave text-advertencia",
  finalizado: "bg-finalizado-suave text-finalizado",
  acento: "bg-acento-suave text-tinta",
} as const;

export interface ChipProps {
  tono?: keyof typeof TONOS;
  /** Si viene, el chip se puede quitar con un botón. */
  onQuitar?: () => void;
  etiquetaQuitar?: string;
  children: ReactNode;
}

/** Un estado o una etiqueta corta: siempre con texto, el color solo lo refuerza. */
export function Chip({ tono = "neutro", onQuitar, etiquetaQuitar, children }: ChipProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 self-start rounded-md py-0.5 text-xs font-semibold ${
        onQuitar ? "pr-1 pl-3" : "px-2"
      } ${TONOS[tono]}`}
    >
      {children}
      {onQuitar && (
        <button
          type="button"
          onClick={onQuitar}
          aria-label={etiquetaQuitar}
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md focus-visible:outline-3 focus-visible:outline-foco md:min-h-10 md:min-w-10"
        >
          <span aria-hidden="true">×</span>
        </button>
      )}
    </span>
  );
}
