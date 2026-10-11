import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useSession } from "../stores/session";

/** Avisa al backend y vacía la sesión; si el logout falla (red incluida), la sesión se vacía igual. */
export function useCerrarSesion() {
  const navigate = useNavigate();
  return async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    // Salida voluntaria: RutaProtegida lleva a /login limpio, sin ?next=. El router aplica la navegación como
    // transición y la sesión vacía se renderiza antes, así que navegar antes no alcanza para evitar la carrera.
    useSession.getState().salir();
    navigate("/login", { replace: true });
  };
}
