import { Link } from "react-router-dom";
import { formatearFecha } from "../lib/fechas";
import type { Evento } from "../stores/eventos";
import { InsigniaEstado } from "./InsigniaEstado";

export function EventoCard({ evento }: { evento: Evento }) {
  return (
    <article className="flex flex-col gap-2 rounded-lg border border-gray-200 p-4">
      <InsigniaEstado evento={evento} />
      <h2 className="text-lg font-semibold">
        <Link to={`/eventos/${evento.id}`} className="text-indigo-700 hover:underline">
          {evento.name}
        </Link>
      </h2>
      <time dateTime={evento.start_at} className="text-sm text-gray-600">
        {formatearFecha(evento.start_at)}
      </time>
      {evento.location && <p className="text-sm text-gray-600">{evento.location}</p>}
      <p className="mt-auto text-sm font-medium">Quedan {evento.available_spots} cupos</p>
    </article>
  );
}
