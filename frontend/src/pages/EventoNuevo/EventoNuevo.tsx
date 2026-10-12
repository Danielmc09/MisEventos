import { FormularioEvento } from "../../components/FormularioEvento";
import { tienePermiso } from "../../lib/permisos";
import { useSession } from "../../stores/session";

export default function EventoNuevo() {
  const user = useSession((s) => s.user);
  const puede = tienePermiso(user, "evento:crear");
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-bold">Nuevo evento</h1>
      {puede ? <FormularioEvento /> : <p className="mt-4">No tenés permiso para crear eventos</p>}
    </main>
  );
}
