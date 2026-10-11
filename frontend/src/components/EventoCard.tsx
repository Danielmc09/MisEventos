import { Link } from "react-router-dom";
import { formatearFecha } from "../lib/fechas";
import type { Evento } from "../stores/eventos";

const ESTADOS = {
  PUBLISHED: ["Publicado", "bg-green-100 text-green-800"],
  DRAFT: ["Borrador", "bg-gray-100 text-gray-800"],
  CANCELLED: ["Cancelado", "bg-red-100 text-red-800"],
} as const;

const FINALIZADO = ["Finalizado", "bg-amber-100 text-amber-800"] as const;

export function EventoCard({ evento }: { evento: Evento }) {
  const [estado, tono] = evento.is_finished ? FINALIZADO : ESTADOS[evento.status];
  return (
    <article className="flex flex-col gap-2 rounded-lg border border-gray-200 p-4">
      <span className={`self-start rounded-full px-2 py-0.5 text-xs font-medium ${tono}`}>
        {estado}
      </span>
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
