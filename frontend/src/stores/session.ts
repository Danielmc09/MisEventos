import { create } from "zustand";
import { useEffect } from "react";
import { persist } from "zustand/middleware";
import type { components } from "../api/schema";

export type Usuario = components["schemas"]["PerfilConPermisos"];
export type Permiso = components["schemas"]["Permiso"];

interface SessionState {
  user: Usuario | null;
  accessToken: string | null;
  /** Instante (ms epoch) en que vence el token; null en una sesión de formato viejo. */
  expiresAt: number | null;
  iniciarSesion: (user: Usuario, accessToken: string, expiresIn: number) => void;
  /** true tras un logout voluntario: la ruta protegida no debe recordar adónde volver. */
  saliendo: boolean;
  cerrarSesion: () => void;
  /** Actualiza el nombre del usuario de la sesión, sin tocar el token. */
  actualizarNombre: (nombre: string | null) => void;
  salir: () => void;
}

export const useSession = create<SessionState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      expiresAt: null,
      saliendo: false,
      iniciarSesion: (user, accessToken, expiresIn) =>
        set({ user, accessToken, expiresAt: Date.now() + expiresIn * 1000, saliendo: false }),
      cerrarSesion: () => set({ user: null, accessToken: null, expiresAt: null, saliendo: false }),
      actualizarNombre: (nombre) =>
        set((s) => (s.user ? { user: { ...s.user, full_name: nombre } } : {})),
      salir: () => set({ user: null, accessToken: null, expiresAt: null, saliendo: true }),
    }),
    {
      name: "sesion",
      partialize: ({ user, accessToken, expiresAt }) => ({ user, accessToken, expiresAt }),
    },
  ),
);

/** Los permisos los calcula la API: el cliente solo los lee. Una sesión guardada sin la lista no tiene ninguno. */
export function useTienePermiso(permiso: Permiso): boolean {
  return useSession((s) => s.user?.permisos?.includes(permiso) ?? false);
}

/** Hay sesión si hay token y no venció. Si venció, la vacía. */
export function useSesionVigente() {
  const vigente = useSession((s) => s.accessToken !== null && (s.expiresAt ?? 0) > Date.now());
  const hayToken = useSession((s) => s.accessToken !== null);
  useEffect(() => {
    if (hayToken && !vigente) useSession.getState().cerrarSesion();
  }, [hayToken, vigente]);
  return vigente;
}
