import { disponibilidad } from "../lib/disponibilidad";
import { Chip } from "./ui/Chip";

interface Props {
  capacidad: number;
  libres: number;
}

/** "Últimos lugares" o "Sin cupos" según lo que queda; nada si hay de sobra. */
export function ChipDisponibilidad({ capacidad, libres }: Props) {
  const estado = disponibilidad(capacidad, libres);
  if (estado === "agotado") return <Chip tono="error">Sin cupos</Chip>;
  if (estado === "ultimos") return <Chip tono="advertencia">Últimos lugares</Chip>;
  return null;
}
