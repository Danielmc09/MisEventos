import { Link } from "react-router-dom";
import type { Usuario } from "../../stores/session";
import { useSession } from "../../stores/session";
import { Button } from "../../components/ui/Button";
import { Toast } from "../../components/ui/Toast";
import { useAvisoUnico } from "../../lib/useAvisoUnico";
import { useCerrarSesion } from "../../lib/useCerrarSesion";

const ROLES: Record<Usuario["role"], string> = {
  ATTENDEE: "Asistente",
  ORGANIZER: "Organizador",
  ADMIN: "Administrador",
};

export default function Perfil() {
  const user = useSession((s) => s.user);
  const cerrarSesion = useCerrarSesion();
  const [aviso] = useAvisoUnico();
  if (!user) return null;
  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-2xl font-bold">Perfil</h1>
      {aviso && <Toast tone="exito" message={aviso} />}
      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
        <dt className="font-medium">Correo electrónico</dt>
        <dd className="break-all">{user.email}</dd>
        <dt className="font-medium">Nombre</dt>
        <dd>{user.full_name ?? "—"}</dd>
        <dt className="font-medium">Rol</dt>
        <dd>{ROLES[user.role]}</dd>
      </dl>
      <p className="mt-4">
        <Link to="/cambiar-contrasena" className="text-indigo-700 underline">
          Cambiar contraseña
        </Link>
      </p>
      <Button type="button" className="mt-4" onClick={cerrarSesion}>
        Cerrar sesión
      </Button>
    </main>
  );
}
