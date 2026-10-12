import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { components } from "../api/schema";

export type Sesion = components["schemas"]["SesionConCupo"];
/** Lo que devuelven crear y editar una sesión: sin las reservas. */
export type SesionGuardada = components["schemas"]["SesionSalida"];

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
  /** Vuelve a pedir las sesiones: el estado del servidor manda. */
  async function refrescar() {
    try {
      const sesiones = await api<Sesion[]>(`/events/${id}/sessions`);
      setCarga({ id: id!, sesiones });
    } catch {
      // Se conserva lo que ya se mostraba.
    }
  }
  const cambiar = (f: (sesiones: Sesion[]) => Sesion[]) =>
    setCarga((c) => c && { ...c, sesiones: f(c.sesiones ?? []) });
  return {
    cargando: !actual,
    sesiones: actual?.sesiones,
    error: actual?.error,
    refrescar,
    /**
     * Agrega la sesión, o actualiza la que tenga el mismo id. El servicio de edición no devuelve
     * las reservas: se conservan las que ya había y los lugares se recalculan.
     */
    guardar: (guardada: SesionGuardada, capacidadEvento: number) =>
      cambiar((lista) => {
        const previa = lista.find((s) => s.id === guardada.id);
        const reservadas = previa?.reserved_count ?? 0;
        const nueva: Sesion = {
          is_reserved: false,
          ...previa,
          ...guardada,
          reserved_count: reservadas,
          available_spots: (guardada.capacity ?? capacidadEvento) - reservadas,
        };
        return previa ? lista.map((s) => (s.id === guardada.id ? nueva : s)) : [...lista, nueva];
      }),
    quitar: (sesionId: string) => cambiar((lista) => lista.filter((s) => s.id !== sesionId)),
    /** Refleja una reserva hecha (o cancelada) sin volver a pedir la lista. */
    marcarReserva: (sesionId: string, reservada: boolean) =>
      cambiar((lista) =>
        lista.map((s) =>
          s.id === sesionId
            ? {
                ...s,
                is_reserved: reservada,
                reserved_count: s.reserved_count + (reservada ? 1 : -1),
                available_spots: s.available_spots + (reservada ? -1 : 1),
              }
            : s,
        ),
      ),
  };
}
