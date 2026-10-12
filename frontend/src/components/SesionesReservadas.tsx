import type { components } from "../api/schema";
import { horaBogota } from "../lib/fechas";
import { Lista } from "./ui/Lista";

type Reservada = components["schemas"]["SesionReservada"];

/** Las sesiones que la persona reservó dentro de una inscripción, en el orden en que llegan. */
export function SesionesReservadas({
  evento,
  sesiones,
}: {
  evento: string;
  sesiones: Reservada[];
}) {
  if (sesiones.length === 0) return null;
  return (
    <Lista etiqueta={`Sesiones reservadas en ${evento}`}>
      {sesiones.map((s) => (
        <li key={s.id}>
          {s.title}, {horaBogota(s.start_at)} a {horaBogota(s.end_at)}, {s.room ?? "Sin sala"}
        </li>
      ))}
    </Lista>
  );
}
