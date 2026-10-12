import { Link } from "react-router-dom";
import { formatearFecha } from "../lib/fechas";
import type { components } from "../api/schema";
import type { Evento } from "../stores/eventos";
import { InsigniaEstado } from "./InsigniaEstado";

type Resumen = components["schemas"]["ResumenEvento"];

/** Un evento del listado (con cupos) o el resumen que trae una inscripción (sin cupos). */
export function EventoCard({ evento }: { evento: Evento | Resumen }) {
  return (
    <article className="flex flex-col gap-2 rounded-lg border border-gray-200 p-4">
      <InsigniaEstado
        evento={evento}
        etiquetaCancelado={"available_spots" in evento ? undefined : "Evento cancelado"}
      />
      <h2 className="text-lg font-semibold">
        <Link to={`/eventos/${evento.id}`} className="text-indigo-700 hover:underline">
          {evento.name}
        </Link>
      </h2>
      <time dateTime={evento.start_at} className="text-sm text-gray-600">
        {formatearFecha(evento.start_at)}
      </time>
      {evento.location && <p className="text-sm text-gray-600">{evento.location}</p>}
      {"available_spots" in evento && (
        <p className="mt-auto text-sm font-medium">Quedan {evento.available_spots} cupos</p>
      )}
    </article>
  );
}
