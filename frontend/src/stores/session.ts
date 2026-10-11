import { create } from "zustand";
import type { components } from "../api/schema";

export type Usuario = components["schemas"]["UsuarioSalida"];

interface SessionState {
  user: Usuario | null;
  accessToken: string | null;
  setToken: (token: string) => void;
  clear: () => void;
  iniciarSesion: (user: Usuario, accessToken: string) => void;
  cerrarSesion: () => void;
}

export const useSession = create<SessionState>((set) => ({
  user: null,
  accessToken: null,
  setToken: (accessToken) => set({ accessToken }),
  clear: () => set({ accessToken: null }),
  iniciarSesion: (user, accessToken) => {
    void user;
    void accessToken;
  },
  cerrarSesion: () => {
    void set;
  },
}));
