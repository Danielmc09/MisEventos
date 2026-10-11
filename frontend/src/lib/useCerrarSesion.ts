import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useSession } from "../stores/session";

/** Avisa al backend y vacía la sesión; si el logout falla (red incluida), la sesión se vacía igual. */
export function useCerrarSesion() {
  const navigate = useNavigate();
  return async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    useSession.getState().cerrarSesion();
    navigate("/login"); // desde una ruta protegida, RutaProtegida puede sumar ?next=<ruta actual>
  };
}
