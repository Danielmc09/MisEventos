import { FormularioEvento } from "../../components/FormularioEvento";
import { useTienePermiso } from "../../stores/session";

export default function EventoNuevo() {
  const puede = useTienePermiso("evento:crear");
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-bold">Nuevo evento</h1>
      {puede ? <FormularioEvento /> : <p className="mt-4">No tenés permiso para crear eventos</p>}
    </main>
  );
}
