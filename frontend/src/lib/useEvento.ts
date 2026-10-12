import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { Evento } from "../stores/eventos";

interface Carga {
  id: string;
  evento?: Evento;
  error?: ApiError;
}

/** Pide un evento. `cargando` es true hasta que llegue el de este `id`. */
export function useEvento(id: string | undefined) {
  const [carga, setCarga] = useState<Carga | null>(null);
  useEffect(() => {
    let vigente = true;
    api<Evento>(`/events/${id}`).then(
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
  const actual = carga?.id === id ? carga : null;
  return {
    cargando: !actual,
    evento: actual?.evento,
    error: actual?.error,
    setEvento: (evento: Evento) => setCarga({ id: evento.id, evento }),
  };
}
