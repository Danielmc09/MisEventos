import { useCerrarSesion } from "../lib/useCerrarSesion";
import { useSesionVigente, useSession, useTienePermiso } from "../stores/session";
import { Enlace } from "./ui/Enlace";
import { MenuAcciones, type ItemMenu } from "./ui/MenuAcciones";

export function Encabezado() {
  const user = useSession((s) => s.user);
  const puedeCrear = useTienePermiso("evento:crear");
  const puedeAdministrar = useTienePermiso("usuarios:gestionar");
  const vigente = useSesionVigente();
  const cerrarSesion = useCerrarSesion();
  const nombre = user && (user.full_name || user.email);
  const sesion = !!user && vigente;

  const itemsCuenta: ItemMenu[] = [
    ...(puedeAdministrar ? [{ texto: "Administración", to: "/admin/usuarios" }] : []),
    { texto: "Mi perfil", to: "/perfil" },
    { texto: "Cerrar sesión", onSelect: cerrarSesion, separado: true },
  ];

  return (
    <header className="bg-panel shadow-tarjeta">
      {/* Siempre en una línea y de 4 rem: los avisos arrancan justo debajo. */}
      <nav
        aria-label="Principal"
        className="mx-auto flex h-16 max-w-6xl flex-nowrap items-center gap-x-4 px-4 md:px-6"
      >
        <div className="mr-auto min-w-0 shrink-0">
          <Enlace to="/" variante="marca">
            Mis Eventos
          </Enlace>
        </div>
        {sesion ? (
          <>
            {puedeCrear && (
              <Enlace to="/eventos/nuevo" variante="navegacion">
                Crear evento
              </Enlace>
            )}
            <MenuAcciones
              etiqueta="Menú de la cuenta"
              variante="circulo"
              alinear="fin"
              titulo={nombre ?? undefined}
              subtitulo={user.full_name ? user.email : undefined}
              items={itemsCuenta}
            >
              {(nombre ?? "?").charAt(0).toLocaleUpperCase("es")}
            </MenuAcciones>
          </>
        ) : (
          <>
            <Enlace to="/login" variante="navegacion">
              Ingresar
            </Enlace>
            <Enlace to="/registro" variante="navegacionOpcional">
              Registrarse
            </Enlace>
          </>
        )}
      </nav>
    </header>
  );
}
