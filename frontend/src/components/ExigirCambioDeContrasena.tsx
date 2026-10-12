import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useSesionVigente, useSession } from "../stores/session";

export const RUTA_CAMBIO = "/cambiar-contrasena";

/** Con una contraseña temporal pendiente, la única pantalla posible es la de cambiarla. */
export function ExigirCambioDeContrasena() {
  const vigente = useSesionVigente();
  const pendiente = useSession((s) => s.user?.must_change_password ?? false);
  const { pathname } = useLocation();
  if (vigente && pendiente && pathname !== RUTA_CAMBIO)
    return <Navigate to={RUTA_CAMBIO} replace />;
  return <Outlet />;
}
