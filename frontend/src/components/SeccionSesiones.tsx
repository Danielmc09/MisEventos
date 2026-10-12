import { useState } from "react";
import { api } from "../api/client";
import { ApiError, type SesionEnConflicto } from "../api/errors";
import { diaBogota, etiquetaDia, horaBogota } from "../lib/fechas";
import type { Sesion, SesionGuardada } from "../lib/useSesiones";
import type { Evento } from "../stores/eventos";
import { ControlReserva } from "./ControlReserva";
import { FormularioSesion } from "./FormularioSesion";
import { AlertaError } from "./ui/AlertaError";
import { Button } from "./ui/Button";
import { DialogoConfirmacion } from "./ui/DialogoConfirmacion";
import { Modal } from "./ui/Modal";
import { Spinner } from "./ui/Spinner";
import { Toast, type ToastProps } from "./ui/Toast";

interface Props {
  cargando: boolean;
  sesiones?: Sesion[];
  error?: ApiError;
  evento: Pick<Evento, "id" | "start_at" | "end_at" | "capacity">;
  /** El dueño del evento o el admin, y el evento todavía admite cambios. */
  puede: boolean;
  /** Se llama con la sesión que el servidor creó o actualizó. */
  onGuardada: (sesion: SesionGuardada) => void;
  /** Se llama cuando el servidor confirmó el borrado. */
  onEliminada: (id: string) => void;
  /** Hay una sesión iniciada y la persona está inscrita al evento. */
  inscrito: boolean;
  eventoPublicado: boolean;
  /** Se llama cuando el servidor confirmó que la reserva se hizo (`true`) o se canceló (`false`). */
  onReserva: (id: string, reservada: boolean) => void;
  /** Vuelve a pedir las sesiones: el servidor tiene otro estado del que se mostraba. */
  onRefrescar: () => void;
}

interface ErrorReserva {
  id: string;
  title: string;
  detalle?: string;
}

const lineaDeConflicto = (c: SesionEnConflicto) =>
  `Ya reservaste «${c.title}», ${horaBogota(c.start_at)} a ${horaBogota(c.end_at)}${
    c.room ? `, ${c.room}` : ""
  }`;

function agruparPorDia(sesiones: Sesion[]) {
  const ordenadas = [...sesiones].sort((a, b) => a.start_at.localeCompare(b.start_at));
  const dias = new Map<string, Sesion[]>();
  for (const s of ordenadas) {
    const dia = diaBogota(s.start_at);
    dias.set(dia, [...(dias.get(dia) ?? []), s]);
  }
  return [...dias.entries()];
}

/** `null`: cerrado. `"nueva"`: crear. Una sesión: editarla. */
type Formulario = "nueva" | Sesion | null;

export function SeccionSesiones({
  cargando,
  sesiones,
  error,
  evento,
  puede,
  onGuardada,
  onEliminada,
  inscrito,
  eventoPublicado,
  onReserva,
  onRefrescar,
}: Props) {
  const [formulario, setFormulario] = useState<Formulario>(null);
  const [pendiente, setPendiente] = useState<Sesion | null>(null);
  const [trabajando, setTrabajando] = useState(false);
  const [reservando, setReservando] = useState<string | null>(null);
  const [errorReserva, setErrorReserva] = useState<ErrorReserva | null>(null);
  const [aviso, setAviso] = useState<Pick<ToastProps, "message" | "tone"> | null>(null);

  async function eliminar(sesion: Sesion) {
    setTrabajando(true);
    try {
      await api<void>(`/sessions/${sesion.id}`, { method: "DELETE" });
      onEliminada(sesion.id);
      setAviso({ message: "Sesión eliminada", tone: "exito" });
    } catch (e) {
      const title = e instanceof ApiError ? e.title : "Ocurrió un error inesperado";
      setAviso({ message: title, tone: "error" });
    } finally {
      setTrabajando(false);
      setPendiente(null);
    }
  }

  async function cambiarReserva(sesion: Sesion, reservar: boolean) {
    setReservando(sesion.id);
    setErrorReserva(null);
    try {
      if (reservar) await api(`/sessions/${sesion.id}/reservations`, { method: "POST" });
      else await api<void>(`/sessions/${sesion.id}/reservations/me`, { method: "DELETE" });
      onReserva(sesion.id, reservar);
    } catch (e) {
      const error = e instanceof ApiError ? e : null;
      const choque = error?.type === "session-conflict";
      setErrorReserva({
        id: sesion.id,
        title: error?.title ?? "Ocurrió un error inesperado",
        detalle: choque ? error.conflicts.map(lineaDeConflicto).join(". ") : undefined,
      });
      // Un choque de horario no cambia lo que se ve; cualquier otro 409 sí.
      if (error?.status === 409 && !choque) onRefrescar();
    } finally {
      setReservando(null);
    }
  }

  return (
    <section aria-labelledby="titulo-sesiones" className="mt-6 flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="titulo-sesiones" className="text-xl font-semibold">
          Sesiones
        </h2>
        {puede && (
          <Button type="button" onClick={() => setFormulario("nueva")}>
            Agregar sesión
          </Button>
        )}
      </div>
      {cargando && (
        <div className="flex justify-center p-6">
          <Spinner />
        </div>
      )}
      {error && (
        <p role="alert" className="text-red-700">
          {error.title}
        </p>
      )}
      {sesiones?.length === 0 && (
        <p className="text-gray-600">Este evento todavía no tiene sesiones</p>
      )}
      {sesiones &&
        agruparPorDia(sesiones).map(([dia, delDia]) => (
          <div key={dia} className="flex flex-col gap-2">
            <h3 className="font-medium text-gray-700">{etiquetaDia(delDia[0].start_at)}</h3>
            <ul className="flex flex-col gap-2">
              {delDia.map((s) => (
                <li key={s.id} className="rounded-md border border-gray-200 p-4">
                  <h4 className="font-semibold">{s.title}</h4>
                  <p>
                    {horaBogota(s.start_at)} a {horaBogota(s.end_at)}
                  </p>
                  {s.room && <p className="text-gray-600">{s.room}</p>}
                  {s.capacity !== null && <p className="text-gray-600">Capacidad: {s.capacity}</p>}
                  {s.speakers.length > 0 && (
                    <p className="text-gray-600">{s.speakers.map((p) => p.full_name).join(", ")}</p>
                  )}
                  <ControlReserva
                    sesion={s}
                    inscrito={inscrito}
                    eventoPublicado={eventoPublicado}
                    trabajando={reservando === s.id}
                    onReservar={() => cambiarReserva(s, true)}
                    onCancelar={() => cambiarReserva(s, false)}
                  />
                  {errorReserva?.id === s.id && (
                    <AlertaError title={errorReserva.title} detail={errorReserva.detalle} />
                  )}
                  {puede && (
                    <div className="mt-2 flex flex-wrap gap-3">
                      <Button
                        type="button"
                        variante="secundario"
                        aria-label={`Editar sesión ${s.title}`}
                        onClick={() => setFormulario(s)}
                      >
                        Editar
                      </Button>
                      <Button
                        type="button"
                        variante="peligro"
                        aria-label={`Eliminar sesión ${s.title}`}
                        onClick={() => setPendiente(s)}
                      >
                        Eliminar
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      {formulario && (
        <Modal
          titulo={formulario === "nueva" ? "Agregar sesión" : "Editar sesión"}
          onCerrar={() => setFormulario(null)}
        >
          <FormularioSesion
            evento={evento}
            sesion={formulario === "nueva" ? undefined : formulario}
            onGuardada={(guardada) => {
              onGuardada(guardada);
              setAviso({
                message: formulario === "nueva" ? "Sesión creada" : "Sesión actualizada",
                tone: "exito",
              });
              setFormulario(null);
            }}
            onCancelar={() => setFormulario(null)}
          />
        </Modal>
      )}
      {pendiente && (
        <DialogoConfirmacion
          titulo="Eliminar la sesión"
          mensaje={`Se borra «${pendiente.title}». No se puede deshacer.`}
          confirmar="Sí, eliminar la sesión"
          cargando={trabajando}
          onConfirmar={() => eliminar(pendiente)}
          onVolver={() => setPendiente(null)}
        />
      )}
      {aviso && (
        <div className="fixed right-4 bottom-4 z-20">
          <Toast {...aviso} onClose={() => setAviso(null)} />
        </div>
      )}
    </section>
  );
}
