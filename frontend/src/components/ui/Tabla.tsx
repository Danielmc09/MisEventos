import type { ReactNode } from "react";

export interface TablaProps {
  descripcion: string;
  columnas: string[];
  filas: { id: string; celdas: ReactNode[] }[];
}

/**
 * En pantallas anchas es una tabla; en las angostas cada fila pasa a ser una tarjeta apilada y cada
 * celda muestra su etiqueta de columna ("Estado: Activa"). Como el cambio de `display` hace que
 * algunos navegadores pierdan la semántica de tabla, los roles van explícitos.
 */
export function Tabla({ descripcion, columnas, filas }: TablaProps) {
  return (
    <div className="overflow-x-auto">
      <table role="table" className="block w-full text-left text-sm md:table">
        <caption className="sr-only">{descripcion}</caption>
        <thead
          role="rowgroup"
          className="hidden border-b border-gray-200 text-gray-700 md:table-header-group"
        >
          <tr role="row">
            {columnas.map((c) => (
              <th key={c} role="columnheader" scope="col" className="px-3 py-2 font-medium">
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
              className="block rounded-md border border-gray-200 p-2 md:table-row md:rounded-none md:border-0 md:border-b md:border-gray-100 md:p-0"
            >
              {f.celdas.map((celda, i) => (
                <td key={i} role="cell" className="block px-3 py-1 md:table-cell md:py-2">
                  <span className="font-medium md:hidden">{columnas[i]}: </span>
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
