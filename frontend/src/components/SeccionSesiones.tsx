import { useState } from "react";
import { api } from "../api/client";
import { ApiError, type SesionEnConflicto } from "../api/errors";
import { diaBogota, etiquetaDia, horaBogota } from "../lib/fechas";
import type { Sesion, SesionGuardada } from "../lib/useSesiones";
import type { Evento } from "../stores/eventos";
import { ControlReserva } from "./ControlReserva";
import { FormularioSesion } from "./FormularioSesion";
import { AlertaError } from "./ui/AlertaError";
import { useAvisos } from "./ui/Avisos";
import { BotonIcono } from "./ui/BotonIcono";
import { Button } from "./ui/Button";
import { IconoLapiz } from "./ui/iconos/IconoLapiz";
import { IconoPapelera } from "./ui/iconos/IconoPapelera";
import { DialogoConfirmacion } from "./ui/DialogoConfirmacion";
import { Modal } from "./ui/Modal";
import { Spinner } from "./ui/Spinner";
import { Tarjeta } from "./ui/Tarjeta";
import { TextoSecundario } from "./ui/TextoSecundario";
import { TituloSeccion } from "./ui/TituloSeccion";

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
  const avisar = useAvisos();

  async function eliminar(sesion: Sesion) {
    setTrabajando(true);
    try {
      await api<void>(`/sessions/${sesion.id}`, { method: "DELETE" });
      onEliminada(sesion.id);
      avisar({ message: "Eliminaste la sesión", tone: "exito" });
    } catch (e) {
      const title = e instanceof ApiError ? e.title : "Ocurrió un error inesperado";
      avisar({ message: title, tone: "error" });
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
      avisar({
        message: reservar ? `Reservaste «${sesion.title}»` : "Cancelaste tu reserva",
        tone: "exito",
      });
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
    <section aria-labelledby="titulo-sesiones" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TituloSeccion id="titulo-sesiones">Sesiones</TituloSeccion>
        {puede && sesiones?.length !== 0 && (
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
      {error && <AlertaError title={error.title} />}
      {sesiones?.length === 0 && (
        <div className="flex flex-col items-start gap-4">
          <TextoSecundario>Este evento todavía no tiene sesiones</TextoSecundario>
          {puede && (
            <Button type="button" onClick={() => setFormulario("nueva")}>
              Agregar sesión
            </Button>
          )}
        </div>
      )}
      {sesiones &&
        agruparPorDia(sesiones).map(([dia, delDia]) => (
          <div key={dia} className="flex flex-col gap-2">
            <TituloSeccion nivel={3} estilo="grupo">
              {etiquetaDia(delDia[0].start_at)}
            </TituloSeccion>
            <ul className="flex flex-col gap-4">
              {delDia.map((s, i) => (
                <Tarjeta as="li" key={s.id} indice={i}>
                  <div className="flex flex-col gap-1">
                    <TituloSeccion nivel={4} estilo="elemento">
                      {s.title}
                    </TituloSeccion>
                    <p>
                      {horaBogota(s.start_at)} a {horaBogota(s.end_at)}
                    </p>
                    {s.room && <TextoSecundario>{s.room}</TextoSecundario>}
                    {s.capacity !== null && (
                      <TextoSecundario>Capacidad: {s.capacity}</TextoSecundario>
                    )}
                    {s.speakers.length > 0 && (
                      <TextoSecundario>
                        {s.speakers.map((p) => p.full_name).join(", ")}
                      </TextoSecundario>
                    )}
                  </div>
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
                    <div className="flex items-center gap-2">
                      <BotonIcono
                        etiqueta={`Editar la sesión «${s.title}»`}
                        texto="Editar"
                        icono={<IconoLapiz />}
                        onClick={() => setFormulario(s)}
                      />
                      <BotonIcono
                        etiqueta={`Eliminar la sesión «${s.title}»`}
                        texto="Eliminar"
                        icono={<IconoPapelera />}
                        variante="peligro"
                        onClick={() => setPendiente(s)}
                      />
                    </div>
                  )}
                </Tarjeta>
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
              avisar({
                message: formulario === "nueva" ? "Creaste la sesión" : "Actualizaste la sesión",
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
    </section>
  );
}
