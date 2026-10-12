import type { ReactNode } from "react";

export interface ListaDatosProps {
  datos: { etiqueta: string; valor: ReactNode }[];
}

/** Pares etiqueta y valor; en pantallas anchas, la etiqueta a la izquierda. */
export function ListaDatos({ datos }: ListaDatosProps) {
  return (
    <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-3">
      {datos.map(({ etiqueta, valor }) => (
        <div key={etiqueta} className="flex flex-col sm:col-span-3 sm:grid sm:grid-cols-subgrid">
          <dt className="font-semibold text-tinta">{etiqueta}</dt>
          <dd className="break-words sm:col-span-2">{valor}</dd>
        </div>
      ))}
    </dl>
  );
}
