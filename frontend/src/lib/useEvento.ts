import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { components } from "../api/schema";
import type { Evento } from "../stores/eventos";

export type EventoDetalle = components["schemas"]["EventoDetalle"];

interface Carga {
  id: string;
  evento?: EventoDetalle;
  error?: ApiError;
}

/** Pide un evento. `cargando` es true hasta que llegue el de este `id`. */
export function useEvento(id: string | undefined) {
  const [carga, setCarga] = useState<Carga | null>(null);
  useEffect(() => {
    let vigente = true;
    api<EventoDetalle>(`/events/${id}`).then(
      (evento) => vigente && setCarga({ id: id!, evento }),
      (e) =>
        vigente &&
        setCarga({
          id: id!,
          error:
            e instanceof ApiError
              ? e
              : new ApiError({
                  status: 0,
                  type: "unknown-error",
                  title: "Ocurrió un error inesperado",
                }),
        }),
    );
    return () => {
      vigente = false;
    };
  }, [id]);
  /** Vuelve a pedir el evento (por ejemplo, tras un 409): el estado del servidor manda. */
  async function refrescar() {
    try {
      const evento = await api<EventoDetalle>(`/events/${id}`);
      setCarga({ id: id!, evento });
    } catch {
      // Se conserva lo que ya se mostraba.
    }
  }
  const actual = carga?.id === id ? carga : null;
  return {
    cargando: !actual,
    evento: actual?.evento,
    error: actual?.error,
    refrescar,
    /** Las acciones del dueño devuelven el evento sin `is_registered`: se conserva el que ya había. */
    setEvento: (nuevo: Evento | EventoDetalle) =>
      setCarga((previo) => ({
        id: nuevo.id,
        evento: { is_registered: false, ...previo?.evento, ...nuevo },
      })),
  };
}
