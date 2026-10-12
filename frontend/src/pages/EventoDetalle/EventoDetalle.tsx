import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import { ChipCupos } from "../../components/ChipCupos";
import { InsigniaEstado } from "../../components/InsigniaEstado";
import { AlertaError } from "../../components/ui/AlertaError";
import { MenuAcciones } from "../../components/ui/MenuAcciones";
import { DialogoConfirmacion } from "../../components/ui/DialogoConfirmacion";
import { EnlaceBoton } from "../../components/ui/EnlaceBoton";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";
import { Spinner } from "../../components/ui/Spinner";
import { Tarjeta } from "../../components/ui/Tarjeta";
import { TextoSecundario } from "../../components/ui/TextoSecundario";
import { formatearFecha } from "../../lib/fechas";
import { SeccionSesiones } from "../../components/SeccionSesiones";
import { useAvisos } from "../../components/ui/Avisos";
import { PanelInscripciones } from "../../components/PanelInscripciones";
import { AccionInscripcion } from "../../components/AccionInscripcion";
import { useEvento } from "../../lib/useEvento";
import { useSesiones } from "../../lib/useSesiones";
import { useEventos, type Evento } from "../../stores/eventos";
import { useSession, useTienePermiso } from "../../stores/session";

type Accion = "publish" | "unpublish" | "cancel" | "delete";

const EXITO: Record<Accion, string> = {
  publish: "Publicaste el evento",
  unpublish: "Despublicaste el evento",
  cancel: "Cancelaste el evento",
  delete: "Eliminaste el evento",
};

const CONFIRMACION = {
  cancel: {
    titulo: "Cancelar el evento",
    mensaje: "Un evento cancelado no se puede volver a publicar.",
    confirmar: "Sí, cancelar el evento",
  },
  delete: {
    titulo: "Eliminar el evento",
    mensaje: "Se borra el evento con sus sesiones. No se puede deshacer.",
    confirmar: "Sí, eliminar el evento",
  },
} as const;

export default function EventoDetalle() {
  const { id } = useParams();
  const { cargando, evento, error, setEvento, refrescar } = useEvento(id);
  const sesiones = useSesiones(id);
  const navigate = useNavigate();
  const user = useSession((s) => s.user);
  const invalidar = useEventos((s) => s.invalidar);
  const [pendiente, setPendiente] = useState<"cancel" | "delete" | null>(null);
  const [trabajando, setTrabajando] = useState(false);
  const avisar = useAvisos();

  const gestionaTodos = useTienePermiso("evento:gestionar_todos");
  const puede = !!evento && !!user && (gestionaTodos || user.id === evento.organizer_id);

  const reservas = sesiones.sesiones?.filter((s) => s.is_reserved).length ?? 0;

  async function ejecutar(accion: Accion) {
    setTrabajando(true);
    try {
      if (accion === "delete") {
        await api<void>(`/events/${id}`, { method: "DELETE" });
        invalidar();
        avisar({ message: EXITO.delete, tone: "exito" });
        navigate("/");
        return;
      }
      setEvento(await api<Evento>(`/events/${id}/${accion}`, { method: "POST" }));
      invalidar();
      avisar({ message: EXITO[accion], tone: "exito" });
    } catch (e) {
      const title = e instanceof ApiError ? e.title : "Ocurrió un error inesperado";
      avisar({ message: title, tone: "error" });
    } finally {
      setTrabajando(false);
      setPendiente(null);
    }
  }

  return (
    <Pagina>
      {cargando && (
        <div className="flex justify-center p-10">
          <Spinner />
        </div>
      )}
      {error && (
        <AlertaError title={error.status === 404 ? "No encontramos este evento" : error.title} />
      )}
      {evento && (
        <>
          <Tarjeta as="div">
            <div className="flex flex-col gap-2">
              <InsigniaEstado evento={evento} />
              <TituloPagina>{evento.name}</TituloPagina>
              <p>
                <time dateTime={evento.start_at}>{formatearFecha(evento.start_at)}</time>
                {" – "}
                <time dateTime={evento.end_at}>{formatearFecha(evento.end_at)}</time>
              </p>
              {evento.location && <TextoSecundario>{evento.location}</TextoSecundario>}
              {evento.description && (
                <p className="break-words whitespace-pre-line">{evento.description}</p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {evento.status !== "CANCELLED" && !evento.is_finished && (
                <ChipCupos
                  capacidad={evento.capacity}
                  libres={evento.available_spots}
                  soloConteo={evento.status === "DRAFT"}
                />
              )}
              <AccionInscripcion
                evento={evento}
                onEvento={setEvento}
                onRefrescar={refrescar}
                reservas={reservas}
                onCancelada={sesiones.refrescar}
              />
            </div>
            {puede && (
              <div className="flex items-center gap-3">
                {evento.status !== "CANCELLED" && !evento.is_finished && (
                  <EnlaceBoton to={`/eventos/${evento.id}/editar`}>Editar</EnlaceBoton>
                )}
                <MenuAcciones
                  etiqueta="Más acciones"
                  ocupado={trabajando}
                  items={[
                    ...(evento.status === "DRAFT" && !evento.is_finished
                      ? [{ texto: "Publicar", onSelect: () => ejecutar("publish") }]
                      : []),
                    ...(evento.status === "PUBLISHED"
                      ? [{ texto: "Despublicar", onSelect: () => ejecutar("unpublish") }]
                      : []),
                    ...(evento.status !== "CANCELLED" && !evento.is_finished
                      ? [
                          {
                            texto: "Cancelar evento",
                            onSelect: () => setPendiente("cancel"),
                            peligro: true,
                          },
                        ]
                      : []),
                    { texto: "Eliminar", onSelect: () => setPendiente("delete"), peligro: true },
                  ]}
                >
                  Más acciones
                </MenuAcciones>
              </div>
            )}
          </Tarjeta>
          {puede && <PanelInscripciones eventoId={evento.id} version={evento.registered_count} />}
          <SeccionSesiones
            cargando={sesiones.cargando}
            sesiones={sesiones.sesiones}
            error={sesiones.error}
            evento={evento}
            // Un evento cancelado o finalizado ya no admite cambios en sus sesiones.
            puede={puede && evento.status !== "CANCELLED" && !evento.is_finished}
            onGuardada={(guardada) => sesiones.guardar(guardada, evento.capacity)}
            onEliminada={sesiones.quitar}
            inscrito={!!user && evento.is_registered}
            eventoPublicado={evento.status === "PUBLISHED"}
            onReserva={sesiones.marcarReserva}
            onRefrescar={sesiones.refrescar}
          />
        </>
      )}
      {pendiente && (
        <DialogoConfirmacion
          {...CONFIRMACION[pendiente]}
          cargando={trabajando}
          onConfirmar={() => ejecutar(pendiente)}
          onVolver={() => setPendiente(null)}
        />
      )}
    </Pagina>
  );
}
