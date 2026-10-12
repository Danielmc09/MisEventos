import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import { InsigniaEstado } from "../../components/InsigniaEstado";
import { Button } from "../../components/ui/Button";
import { DialogoConfirmacion } from "../../components/ui/DialogoConfirmacion";
import { Spinner } from "../../components/ui/Spinner";
import { formatearFecha } from "../../lib/fechas";
import { SeccionSesiones } from "../../components/SeccionSesiones";
import { Toast, type ToastProps } from "../../components/ui/Toast";
import { PanelInscripciones } from "../../components/PanelInscripciones";
import { AccionInscripcion } from "../../components/AccionInscripcion";
import { quedan } from "../../lib/plural";
import { useEvento } from "../../lib/useEvento";
import { useSesiones } from "../../lib/useSesiones";
import { useEventos, type Evento } from "../../stores/eventos";
import { useSession, useTienePermiso } from "../../stores/session";

type Accion = "publish" | "unpublish" | "cancel" | "delete";

const EXITO: Record<Accion, string> = {
  publish: "Evento publicado",
  unpublish: "Evento despublicado",
  cancel: "Evento cancelado",
  delete: "Evento eliminado",
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
  const [aviso, setAviso] = useState<Pick<ToastProps, "message" | "tone"> | null>(null);

  const gestionaTodos = useTienePermiso("evento:gestionar_todos");
  const puede = !!evento && !!user && (gestionaTodos || user.id === evento.organizer_id);

  const reservas = sesiones.sesiones?.filter((s) => s.is_reserved).length ?? 0;

  async function ejecutar(accion: Accion) {
    setTrabajando(true);
    try {
      if (accion === "delete") {
        await api<void>(`/events/${id}`, { method: "DELETE" });
        invalidar();
        navigate("/");
        return;
      }
      setEvento(await api<Evento>(`/events/${id}/${accion}`, { method: "POST" }));
      invalidar();
      setAviso({ message: EXITO[accion], tone: "exito" });
    } catch (e) {
      const title = e instanceof ApiError ? e.title : "Ocurrió un error inesperado";
      setAviso({ message: title, tone: "error" });
    } finally {
      setTrabajando(false);
      setPendiente(null);
    }
  }

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
          <p className="font-medium">{quedan(evento.available_spots, "cupo", "cupos")}</p>
          <div className="flex flex-wrap items-center gap-3">
            <AccionInscripcion
              evento={evento}
              onEvento={setEvento}
              onRefrescar={refrescar}
              onAviso={setAviso}
              reservas={reservas}
              onCancelada={sesiones.refrescar}
            />
          </div>
          {puede && (
            <div className="mt-2 flex flex-wrap gap-3">
              {evento.status !== "CANCELLED" && !evento.is_finished && (
                <Link
                  to={`/eventos/${evento.id}/editar`}
                  className="rounded-md border border-gray-300 px-4 py-2"
                >
                  Editar
                </Link>
              )}
              {evento.status === "DRAFT" && !evento.is_finished && (
                <Button loading={trabajando} onClick={() => ejecutar("publish")}>
                  Publicar
                </Button>
              )}
              {evento.status === "PUBLISHED" && (
                <Button loading={trabajando} onClick={() => ejecutar("unpublish")}>
                  Despublicar
                </Button>
              )}
              {evento.status !== "CANCELLED" && !evento.is_finished && (
                <Button variante="peligro" onClick={() => setPendiente("cancel")}>
                  Cancelar
                </Button>
              )}
              <Button variante="peligro" onClick={() => setPendiente("delete")}>
                Eliminar
              </Button>
            </div>
          )}
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
      {aviso && (
        <div className="fixed right-4 bottom-4 z-20">
          <Toast {...aviso} onClose={() => setAviso(null)} />
        </div>
      )}
    </main>
  );
}
