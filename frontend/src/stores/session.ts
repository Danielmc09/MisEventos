import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { components } from "../api/schema";

export type Usuario = components["schemas"]["UsuarioSalida"];

interface SessionState {
  user: Usuario | null;
  accessToken: string | null;
  iniciarSesion: (user: Usuario, accessToken: string) => void;
  /** true tras un logout voluntario: la ruta protegida no debe recordar adónde volver. */
  saliendo: boolean;
  cerrarSesion: () => void;
  salir: () => void;
}

export const useSession = create<SessionState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      saliendo: false,
      iniciarSesion: (user, accessToken) => set({ user, accessToken, saliendo: false }),
      cerrarSesion: () => set({ user: null, accessToken: null, saliendo: false }),
      salir: () => set({ user: null, accessToken: null, saliendo: true }),
    }),
    {
      name: "sesion",
      partialize: ({ user, accessToken }) => ({ user, accessToken }),
    },
  ),
);
