import type { ReactNode } from "react";

export interface TablaProps {
  descripcion: string;
  columnas: string[];
  filas: { id: string; celdas: ReactNode[] }[];
}

export function Tabla({ descripcion, columnas, filas }: TablaProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{descripcion}</caption>
        <thead className="border-b border-gray-200 text-gray-700">
          <tr>
            {columnas.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.id} className="border-b border-gray-100">
              {f.celdas.map((celda, i) => (
                <td key={i} className="px-3 py-2">
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
