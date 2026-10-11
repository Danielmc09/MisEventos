import { create } from "zustand";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type Evento = components["schemas"]["EventoSalida"];
export type PaginaEventos = components["schemas"]["Pagina_EventoSalida_"];

interface EventosState {
  listar: (consulta: string) => Promise<PaginaEventos>;
  invalidar: () => void;
}

export const useEventos = create<EventosState>()(() => ({
  listar: (consulta) => api<PaginaEventos>(`/events?${consulta}`),
  invalidar: () => {},
}));
