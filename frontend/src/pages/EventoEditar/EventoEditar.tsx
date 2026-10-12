import { useParams } from "react-router-dom";
import { FormularioEvento } from "../../components/FormularioEvento";
import { Spinner } from "../../components/ui/Spinner";
import { useEvento } from "../../lib/useEvento";
import { useSession } from "../../stores/session";

export default function EventoEditar() {
  const { id } = useParams();
  const { cargando, evento, error } = useEvento(id);
  const user = useSession((s) => s.user);
  const puede = evento && user && (user.role === "ADMIN" || user.id === evento.organizer_id);

  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-bold">Editar evento</h1>
      {cargando && (
        <div className="flex justify-center p-10">
          <Spinner />
        </div>
      )}
      {error && (
        <p role="alert" className="mt-4 text-red-700">
          {error.status === 404 ? "No encontramos este evento" : error.title}
        </p>
      )}
      {evento && !puede && <p className="mt-4">No tenés permiso para editar este evento</p>}
      {evento && puede && <FormularioEvento evento={evento} />}
    </main>
  );
}
