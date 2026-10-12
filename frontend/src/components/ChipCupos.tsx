import { disponibilidad } from "../lib/disponibilidad";
import { quedan } from "../lib/plural";
import { Chip } from "./ui/Chip";

interface Props {
  capacidad: number;
  libres: number;
  /** Los eventos hablan de cupos; las sesiones, de lugares. */
  unidad?: "cupo" | "lugar";
}

/** El único chip de cupos: "Sin cupos", "Últimos lugares · queda 1" o "Quedan N cupos". */
export function ChipCupos({ capacidad, libres, unidad = "cupo" }: Props) {
  const estado = disponibilidad(capacidad, libres);
  if (estado === "agotado") return <Chip tono="error">Sin cupos</Chip>;
  if (estado === "ultimos") {
    return (
      <Chip tono="advertencia">
        Últimos lugares · {libres === 1 ? "queda" : "quedan"} {libres}
      </Chip>
    );
  }
  return (
    <Chip tono="acento">{quedan(libres, unidad, unidad === "cupo" ? "cupos" : "lugares")}</Chip>
  );
}
