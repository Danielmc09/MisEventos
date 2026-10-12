import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { components } from "../api/schema";

export type Sesion = components["schemas"]["SesionSalida"];

interface Carga {
  id: string;
  sesiones?: Sesion[];
  error?: ApiError;
}

/** Pide las sesiones de un evento, aparte del evento. `cargando` es true hasta que lleguen las de este `id`. */
export function useSesiones(id: string | undefined) {
  const [carga, setCarga] = useState<Carga | null>(null);
  useEffect(() => {
    let vigente = true;
    api<Sesion[]>(`/events/${id}/sessions`).then(
      (sesiones) => vigente && setCarga({ id: id!, sesiones }),
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
    sesiones: actual?.sesiones,
    error: actual?.error,
    /** Agrega la sesión, o reemplaza la que tenga el mismo id. */
    guardar: (sesion: Sesion) =>
      setCarga(
        (c) =>
          c && {
            ...c,
            sesiones: c.sesiones?.some((s) => s.id === sesion.id)
              ? c.sesiones.map((s) => (s.id === sesion.id ? sesion : s))
              : [...(c.sesiones ?? []), sesion],
          },
      ),
    quitar: (sesionId: string) =>
      setCarga((c) => c && { ...c, sesiones: c.sesiones?.filter((s) => s.id !== sesionId) }),
  };
}
