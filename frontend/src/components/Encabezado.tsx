import { useCerrarSesion } from "../lib/useCerrarSesion";
import { useEsAngosto } from "../lib/useEsAngosto";
import { useSesionVigente, useSession, useTienePermiso } from "../stores/session";
import { Enlace } from "./ui/Enlace";
import { MenuAcciones, type ItemMenu } from "./ui/MenuAcciones";

export function Encabezado() {
  const user = useSession((s) => s.user);
  const puedeCrear = useTienePermiso("evento:crear");
  const vigente = useSesionVigente();
  const cerrarSesion = useCerrarSesion();
  const angosto = useEsAngosto();
  const nombre = user && (user.full_name || user.email);
  const sesion = !!user && vigente;

  const itemsCuenta: ItemMenu[] = [
    { texto: "Mi perfil", to: "/perfil" },
    { texto: "Cambiar contraseña", to: "/cambiar-contrasena" },
    { texto: "Cerrar sesión", onSelect: cerrarSesion, separado: true },
  ];

  const itemsVisitante: ItemMenu[] = [
    { texto: "Iniciar sesión", to: "/login" },
    { texto: "Registrarse", to: "/registro" },
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
        ) : angosto ? (
          // «Mis Eventos», «Iniciar sesión» y «Registrarse» miden unos 347 px con sus márgenes: en 320 px no entran.
          <MenuAcciones etiqueta="Menú de la cuenta" alinear="fin" items={itemsVisitante}>
            Entrar
          </MenuAcciones>
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
