import { create } from "zustand";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useSession } from "./session";

export type Evento = components["schemas"]["EventoSalida"];
export type PaginaEventos = components["schemas"]["Pagina_EventoSalida_"];

const VIGENCIA_MS = 60_000;

interface EventosState {
  /** Páginas ya pedidas, por combinación de filtros (la query string). */
  list: Record<string, { pagina: PaginaEventos; en: number }>;
  listar: (consulta: string) => Promise<PaginaEventos>;
  /** Crear, editar y cambiar el estado la llaman para que el listado se vuelva a pedir. */
  invalidar: () => void;
}

export const useEventos = create<EventosState>()((set, get) => ({
  list: {},
  listar: async (consulta) => {
    const guardada = get().list[consulta];
    if (guardada && Date.now() - guardada.en < VIGENCIA_MS) return guardada.pagina;
    const pagina = await api<PaginaEventos>(`/events?${consulta}`);
    set((s) => ({ list: { ...s.list, [consulta]: { pagina, en: Date.now() } } }));
    return pagina;
  },
  invalidar: () => set({ list: {} }),
}));

// El listado depende de quién consulta (el admin y el organizador ven borradores). Cualquier cambio de
// identidad (login, logout, cierre por 401 o vencimiento) pasa por el store de sesión y vacía la caché.
// Renovar el token del mismo usuario no cambia el id, así que no la vacía.
useSession.subscribe((estado, previo) => {
  if (estado.user?.id !== previo.user?.id) useEventos.getState().invalidar();
});
