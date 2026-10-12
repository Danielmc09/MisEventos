import { useParams } from "react-router-dom";
import { FormularioEvento } from "../../components/FormularioEvento";
import { AlertaError } from "../../components/ui/AlertaError";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";
import { Spinner } from "../../components/ui/Spinner";
import { Tarjeta } from "../../components/ui/Tarjeta";
import { useEvento } from "../../lib/useEvento";
import { useSession, useTienePermiso } from "../../stores/session";

export default function EventoEditar() {
  const { id } = useParams();
  const { cargando, evento, error } = useEvento(id);
  const user = useSession((s) => s.user);
  const gestionaTodos = useTienePermiso("evento:gestionar_todos");
  const puede = evento && user && (gestionaTodos || user.id === evento.organizer_id);

  return (
    <Pagina>
      <TituloPagina>Editar evento</TituloPagina>
      {cargando && (
        <div className="flex justify-center p-10">
          <Spinner />
        </div>
      )}
      {error && (
        <AlertaError title={error.status === 404 ? "No encontramos este evento" : error.title} />
      )}
      {evento && !puede && <p>No tenés permiso para editar este evento</p>}
      {evento && puede && (
        <Tarjeta as="div">
          <FormularioEvento evento={evento} />
        </Tarjeta>
      )}
    </Pagina>
  );
}
