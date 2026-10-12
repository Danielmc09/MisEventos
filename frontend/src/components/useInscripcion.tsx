import { useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { ApiError } from "../api/errors";
import { plural } from "../lib/plural";
import type { EventoDetalle } from "../lib/useEvento";
import { useEventos } from "../stores/eventos";
import { useSession } from "../stores/session";
import { DialogoConfirmacion } from "./ui/DialogoConfirmacion";
import { useAvisos } from "./ui/Avisos";

const avisoReservas = (n: number) =>
  n === 1
    ? "También se cancelará tu reserva de sesión."
    : `También se cancelarán tus ${plural(n, "reserva", "reservas")} de sesiones.`;

interface Opciones {
  evento: EventoDetalle;
  onEvento: (evento: EventoDetalle) => void;
  onRefrescar: () => void;
  /** Cuántas sesiones de este evento tiene reservadas la persona: se cancelan con la inscripción. */
  reservas: number;
  /** Se llama cuando la inscripción se canceló, para que se refresquen las sesiones. */
  onCancelada: () => void;
}

/** La situación de quien mira frente a la inscripción. `cerrado`: ya no se puede inscribir ni cancelar. */
export type SituacionInscripcion = "cerrado" | "anonimo" | "inscrito" | "sin-cupos" | "libre";

export interface Inscripcion {
  situacion: SituacionInscripcion;
  trabajando: boolean;
  inscribirse: () => void;
  /** Abre el diálogo para cancelar la inscripción. */
  pedirCancelar: () => void;
  /** El diálogo de confirmación, o `false`: se pinta una vez, donde sea. */
  dialogo: ReactNode;
}

/** Inscribirse o cancelar la inscripción: la lógica, para que cada pantalla la muestre donde le toque. */
export function useInscripcion({
  evento,
  onEvento,
  onRefrescar,
  reservas,
  onCancelada,
}: Opciones): Inscripcion {
  const user = useSession((s) => s.user);
  const invalidar = useEventos((s) => s.invalidar);
  const avisar = useAvisos();
  const [trabajando, setTrabajando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);

  const cerrado =
    evento.status !== "PUBLISHED" || evento.is_finished || new Date(evento.start_at) <= new Date();
  const situacion: SituacionInscripcion = cerrado
    ? "cerrado"
    : !user
      ? "anonimo"
      : evento.is_registered
        ? "inscrito"
        : evento.available_spots <= 0
          ? "sin-cupos"
          : "libre";

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
      if (accion === "cancelar") onCancelada();
      avisar({
        message:
          accion === "inscribirse" ? "Te inscribiste al evento" : "Cancelaste tu inscripción",
        tone: "exito",
      });
    } catch (e) {
      const error = e instanceof ApiError ? e : null;
      avisar({ message: error?.title ?? "Ocurrió un error inesperado", tone: "error" });
      if (error?.status === 409) onRefrescar();
    } finally {
      setTrabajando(false);
      setConfirmando(false);
    }
  }

  return {
    situacion,
    trabajando,
    inscribirse: () => void ejecutar("inscribirse"),
    pedirCancelar: () => setConfirmando(true),
    dialogo: confirmando && (
      <DialogoConfirmacion
        titulo="Cancelar tu inscripción"
        mensaje={`Vas a liberar tu cupo. Después podés volver a inscribirte si todavía queda lugar.${
          reservas > 0 ? ` ${avisoReservas(reservas)}` : ""
        }`}
        confirmar="Sí, cancelar mi inscripción"
        cargando={trabajando}
        onConfirmar={() => void ejecutar("cancelar")}
        onVolver={() => setConfirmando(false)}
      />
    ),
  };
}
