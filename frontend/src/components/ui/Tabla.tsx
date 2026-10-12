import type { ReactNode } from "react";

export interface TablaProps {
  descripcion: string;
  columnas: string[];
  filas: { id: string; celdas: ReactNode[] }[];
}

/**
 * En pantallas anchas es una tabla; en las angostas cada fila pasa a ser un bloque apilado y cada
 * celda muestra su etiqueta de columna ("Estado: Activa"). Como el cambio de `display` hace que
 * algunos navegadores pierdan la semántica de tabla, los roles van explícitos.
 */
export function Tabla({ descripcion, columnas, filas }: TablaProps) {
  return (
    <div className="md:overflow-x-auto">
      <table role="table" className="block w-full text-left text-sm md:table">
        <caption className="sr-only">{descripcion}</caption>
        <thead
          role="rowgroup"
          className="hidden border-b border-tinta/15 text-tinta md:table-header-group"
        >
          <tr role="row">
            {columnas.map((c) => (
              <th key={c} role="columnheader" scope="col" className="px-3 py-2 font-semibold">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody role="rowgroup" className="flex flex-col gap-3 md:table-row-group">
          {filas.map((f) => (
            <tr
              key={f.id}
              role="row"
              className="block rounded-md bg-fondo p-2 md:table-row md:rounded-none md:bg-transparent md:p-0 md:border-b md:border-tinta/10"
            >
              {f.celdas.map((celda, i) => (
                <td
                  key={i}
                  role="cell"
                  className="block px-3 py-1 break-words md:table-cell md:py-2"
                >
                  <span className="font-semibold text-tinta md:hidden">{columnas[i]}: </span>
                  {celda}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
