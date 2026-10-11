import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useSession } from "../stores/session";

export function RutaProtegida() {
  const hayToken = useSession((s) => s.accessToken !== null);
  const saliendo = useSession((s) => s.saliendo);
  const { pathname, search } = useLocation();
  if (hayToken) return <Outlet />;
  if (saliendo) return <Navigate to="/login" replace />;
  return <Navigate to={`/login?next=${encodeURIComponent(pathname + search)}`} replace />;
}
