import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useSession } from "../stores/session";

export function RutaProtegida() {
  const hayToken = useSession((s) => s.accessToken !== null);
  const { pathname, search } = useLocation();
  if (hayToken) return <Outlet />;
  return <Navigate to={`/login?next=${encodeURIComponent(pathname + search)}`} replace />;
}
