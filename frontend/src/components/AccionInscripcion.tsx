import { useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { ApiError } from "../api/errors";
import { conservarNext } from "../lib/next";
import type { EventoDetalle } from "../lib/useEvento";
import { useEventos } from "../stores/eventos";
import { useSession } from "../stores/session";
import { Button } from "./ui/Button";
import { DialogoConfirmacion } from "./ui/DialogoConfirmacion";
import { EnlaceBoton } from "./ui/EnlaceBoton";
import { Insignia } from "./ui/Insignia";
import type { ToastProps } from "./ui/Toast";

export type Aviso = Pick<ToastProps, "message" | "tone">;

interface Props {
  evento: EventoDetalle;
  onEvento: (evento: EventoDetalle) => void;
  onRefrescar: () => void;
  onAviso: (aviso: Aviso) => void;
}

/** Inscribirse o cancelar la inscripción, según la situación de quien mira y del evento. */
export function AccionInscripcion({ evento, onEvento, onRefrescar, onAviso }: Props) {
  const user = useSession((s) => s.user);
  const invalidar = useEventos((s) => s.invalidar);
  const [trabajando, setTrabajando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);

  const cerrado =
    evento.status !== "PUBLISHED" || evento.is_finished || new Date(evento.start_at) <= new Date();
  if (cerrado) return null;

  if (!user) {
    return (
      <EnlaceBoton to={`/login${conservarNext(`/eventos/${evento.id}`)}`}>
        Iniciá sesión para inscribirte
      </EnlaceBoton>
    );
  }

  async function ejecutar(accion: "inscribirse" | "cancelar") {
    setTrabajando(true);
    const paso = accion === "inscribirse" ? 1 : -1;
    try {
      if (accion === "inscribirse") {
        await api<components["schemas"]["InscripcionSalida"]>(
          `/events/${evento.id}/registrations`,
          { method: "POST" },
        );
      } else {
        await api<void>(`/events/${evento.id}/registrations/me`, { method: "DELETE" });
      }
      onEvento({
        ...evento,
        is_registered: accion === "inscribirse",
        registered_count: evento.registered_count + paso,
        available_spots: evento.available_spots - paso,
      });
      invalidar();
      onAviso({
        message:
          accion === "inscribirse" ? "Te inscribiste al evento" : "Cancelaste tu inscripción",
        tone: "exito",
      });
    } catch (e) {
      const error = e instanceof ApiError ? e : null;
      onAviso({ message: error?.title ?? "Ocurrió un error inesperado", tone: "error" });
      if (error?.status === 409) onRefrescar();
    } finally {
      setTrabajando(false);
      setConfirmando(false);
    }
  }

  if (evento.is_registered) {
    return (
      <>
        <Insignia tono="exito">Estás inscrito</Insignia>
        <Button variante="secundario" onClick={() => setConfirmando(true)}>
          Cancelar inscripción
        </Button>
        {confirmando && (
          <DialogoConfirmacion
            titulo="Cancelar tu inscripción"
            mensaje="Vas a liberar tu cupo. Después podés volver a inscribirte si todavía queda lugar."
            confirmar="Sí, cancelar mi inscripción"
            cargando={trabajando}
            onConfirmar={() => ejecutar("cancelar")}
            onVolver={() => setConfirmando(false)}
          />
        )}
      </>
    );
  }

  if (evento.available_spots <= 0) {
    return <Button disabled>Sin cupos</Button>;
  }

  return (
    <Button loading={trabajando} onClick={() => ejecutar("inscribirse")}>
      Inscribirme
    </Button>
  );
}
