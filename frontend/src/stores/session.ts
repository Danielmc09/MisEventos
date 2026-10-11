import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { components } from "../api/schema";

export type Usuario = components["schemas"]["UsuarioSalida"];

interface SessionState {
  user: Usuario | null;
  accessToken: string | null;
  iniciarSesion: (user: Usuario, accessToken: string) => void;
  cerrarSesion: () => void;
}

export const useSession = create<SessionState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      iniciarSesion: (user, accessToken) => set({ user, accessToken }),
      cerrarSesion: () => set({ user: null, accessToken: null }),
    }),
    {
      name: "sesion",
      partialize: ({ user, accessToken }) => ({ user, accessToken }),
    },
  ),
);
