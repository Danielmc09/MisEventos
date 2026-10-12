import { useParams } from "react-router-dom";
import { InsigniaEstado } from "../../components/InsigniaEstado";
import { Spinner } from "../../components/ui/Spinner";
import { formatearFecha } from "../../lib/fechas";
import { useEvento } from "../../lib/useEvento";

export default function EventoDetalle() {
  const { id } = useParams();
  const { cargando, evento, error } = useEvento(id);

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-3 p-6">
      {cargando && (
        <div className="flex justify-center p-10">
          <Spinner />
        </div>
      )}
      {error && (
        <p role="alert" className="text-red-700">
          {error.status === 404 ? "No encontramos este evento" : error.title}
        </p>
      )}
      {evento && (
        <>
          <InsigniaEstado evento={evento} />
          <h1 className="text-2xl font-bold">{evento.name}</h1>
          <p>
            <time dateTime={evento.start_at}>{formatearFecha(evento.start_at)}</time>
            {" – "}
            <time dateTime={evento.end_at}>{formatearFecha(evento.end_at)}</time>
          </p>
          {evento.location && <p className="text-gray-600">{evento.location}</p>}
          {evento.description && <p className="whitespace-pre-line">{evento.description}</p>}
          <p className="font-medium">Quedan {evento.available_spots} cupos</p>
        </>
      )}
    </main>
  );
}
