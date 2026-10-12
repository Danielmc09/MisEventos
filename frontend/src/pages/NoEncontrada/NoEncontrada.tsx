import { EnlaceBoton } from "../../components/ui/EnlaceBoton";

export default function NoEncontrada() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col items-start gap-4 p-6">
      <h1 className="text-2xl font-bold">No encontramos esa página</h1>
      <EnlaceBoton to="/">Volver al inicio</EnlaceBoton>
    </main>
  );
}
