import { FormularioEvento } from "../../components/FormularioEvento";

export default function EventoNuevo() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-bold">Nuevo evento</h1>
      <FormularioEvento />
    </main>
  );
}
