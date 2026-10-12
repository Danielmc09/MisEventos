import { MisInscripciones } from "../../components/MisInscripciones";
import { EnlaceBoton } from "../../components/ui/EnlaceBoton";
import { ListaDatos } from "../../components/ui/ListaDatos";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";
import { Tarjeta } from "../../components/ui/Tarjeta";
import type { Usuario } from "../../stores/session";
import { useSession } from "../../stores/session";

const ROLES: Record<Usuario["role"], string> = {
  ATTENDEE: "Asistente",
  ORGANIZER: "Organizador",
  ADMIN: "Administrador",
};

export default function Perfil() {
  const user = useSession((s) => s.user);
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
          <EnlaceBoton to="/cambiar-contrasena" variante="secundario">
            Cambiar contraseña
          </EnlaceBoton>
        </div>
      </Tarjeta>
      <MisInscripciones />
    </Pagina>
  );
}
