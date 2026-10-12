export type Disponibilidad = "ultimos" | "agotado" | null;

/**
 * "agotado" sin lugares; "ultimos" cuando quedan hasta el 10 % de la capacidad (mínimo 1 lugar);
 * null en cualquier otro caso.
 */
export function disponibilidad(capacidad: number, libres: number): Disponibilidad {
  if (libres <= 0) return "agotado";
  return libres <= Math.max(1, Math.floor(capacidad * 0.1)) ? "ultimos" : null;
}
