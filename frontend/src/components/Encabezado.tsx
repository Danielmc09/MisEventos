import { useCerrarSesion } from "../lib/useCerrarSesion";
import { useSesionVigente, useSession, useTienePermiso } from "../stores/session";
import { BotonEnlace, Enlace } from "./ui/Enlace";

export function Encabezado() {
  const user = useSession((s) => s.user);
  const puedeCrear = useTienePermiso("evento:crear");
  const vigente = useSesionVigente();
  const cerrarSesion = useCerrarSesion();
  const nombre = user && (user.full_name || user.email);
  return (
    <header className="bg-panel shadow-tarjeta">
      {/* En escritorio mide 4 rem: los avisos arrancan justo debajo. */}
      <nav
        aria-label="Principal"
        className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 md:h-16 md:flex-nowrap md:px-6 md:py-0"
      >
        <div className="mr-auto shrink-0">
          <Enlace to="/" variante="marca">
            Mis Eventos
          </Enlace>
        </div>
        {user && vigente ? (
          <>
            {puedeCrear && (
              <Enlace to="/eventos/nuevo" variante="navegacion">
                Crear evento
              </Enlace>
            )}
            <Enlace to="/perfil" variante="navegacion" title={nombre ?? undefined}>
              {nombre}
            </Enlace>
            <BotonEnlace onClick={cerrarSesion}>Cerrar sesión</BotonEnlace>
          </>
        ) : (
          <>
            <Enlace to="/login" variante="navegacion">
              Iniciar sesión
            </Enlace>
            <Enlace to="/registro" variante="navegacion">
              Registrarse
            </Enlace>
          </>
        )}
      </nav>
    </header>
  );
}
