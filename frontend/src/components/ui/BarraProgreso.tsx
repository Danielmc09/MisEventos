export interface BarraProgresoProps {
  etiqueta: string;
  /** Porcentaje de 0 a 100. */
  valor: number;
}

export function BarraProgreso({ etiqueta, valor }: BarraProgresoProps) {
  const acotado = Math.min(100, Math.max(0, valor));
  return (
    <div
      role="progressbar"
      aria-label={etiqueta}
      aria-valuenow={acotado}
      aria-valuemin={0}
      aria-valuemax={100}
      className="h-3 w-full overflow-hidden rounded-full bg-gray-200"
    >
      <div className="h-full bg-indigo-600" style={{ width: `${acotado}%` }} />
    </div>
  );
}
