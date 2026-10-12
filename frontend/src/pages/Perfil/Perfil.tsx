import { MisInscripciones } from "../../components/MisInscripciones";
import { Button } from "../../components/ui/Button";
import { Enlace } from "../../components/ui/Enlace";
import { ListaDatos } from "../../components/ui/ListaDatos";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";
import { Tarjeta } from "../../components/ui/Tarjeta";
import { useCerrarSesion } from "../../lib/useCerrarSesion";
import type { Usuario } from "../../stores/session";
import { useSession } from "../../stores/session";

const ROLES: Record<Usuario["role"], string> = {
  ATTENDEE: "Asistente",
  ORGANIZER: "Organizador",
  ADMIN: "Administrador",
};

export default function Perfil() {
  const user = useSession((s) => s.user);
  const cerrarSesion = useCerrarSesion();
  if (!user) return null;
  return (
    <Pagina>
      <TituloPagina>Perfil</TituloPagina>
      <Tarjeta as="section" aria-label="Datos de tu cuenta">
        <ListaDatos
          datos={[
            { etiqueta: "Correo electrónico", valor: user.email },
            { etiqueta: "Nombre", valor: user.full_name ?? "—" },
            { etiqueta: "Rol", valor: ROLES[user.role] },
          ]}
        />
        <div className="flex flex-wrap items-center gap-4">
          <Enlace to="/cambiar-contrasena">Cambiar contraseña</Enlace>
          <Button type="button" variante="secundario" onClick={cerrarSesion}>
            Cerrar sesión
          </Button>
        </div>
      </Tarjeta>
      <MisInscripciones />
    </Pagina>
  );
}
