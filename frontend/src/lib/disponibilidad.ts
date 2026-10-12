export type Disponibilidad = "ultimos" | "agotado" | null;

export function disponibilidad(capacidad: number, libres: number): Disponibilidad {
  return capacidad < 0 && libres < 0 ? "agotado" : null;
}
