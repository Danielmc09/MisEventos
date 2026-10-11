import { Link } from "react-router-dom";
import { useCerrarSesion } from "../lib/useCerrarSesion";
import { useSesionVigente, useSession } from "../stores/session";

const enlace = "text-indigo-700 hover:underline";

export function Encabezado() {
  const user = useSession((s) => s.user);
  const vigente = useSesionVigente();
  const cerrarSesion = useCerrarSesion();
  return (
    <header className="border-b border-gray-200">
      <nav
        aria-label="Principal"
        className="mx-auto flex max-w-3xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2"
      >
        <Link to="/" className="mr-auto font-bold">
          Mis Eventos
        </Link>
        {user && vigente ? (
          <>
            <Link to="/perfil" className={`${enlace} max-w-full truncate`}>
              {user.full_name || user.email}
            </Link>
            <button type="button" onClick={cerrarSesion} className={enlace}>
              Cerrar sesión
            </button>
          </>
        ) : (
          <>
            <Link to="/login" className={enlace}>
              Iniciar sesión
            </Link>
            <Link to="/registro" className={enlace}>
              Registrarse
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
