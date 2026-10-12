import { useEffect } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useSession } from "../stores/session";

let enCurso: Promise<void> | null = null;

/** Pide los datos frescos del usuario; una sola petición aunque se llame dos veces seguidas. */
function refrescar(token: string): Promise<void> {
  enCurso ??= api<components["schemas"]["PerfilConPermisos"]>("/auth/me")
    .then((user) => {
      // Si la sesión cambió mientras llegaba la respuesta, esos datos son de otro token.
      if (useSession.getState().accessToken === token) useSession.setState({ user });
    })
    // Un 401 ya cerró la sesión en el cliente; ante un error de red se queda lo guardado.
    .catch(() => undefined)
    .finally(() => {
      enCurso = null;
    });
  return enCurso;
}

/** Al cargar la app, con una sesión guardada vigente, los datos de /auth/me mandan sobre los guardados. */
export function useRefrescarSesion() {
  useEffect(() => {
    const { accessToken, expiresAt } = useSession.getState();
    if (accessToken && (expiresAt ?? 0) > Date.now()) void refrescar(accessToken);
  }, []);
}
