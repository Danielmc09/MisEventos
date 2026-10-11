import { useLocation } from "react-router-dom";
import { Toast } from "../../components/ui/Toast";

export default function Login() {
  const aviso = (useLocation().state as { aviso?: string } | null)?.aviso;
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-bold">Iniciar sesión</h1>
      {aviso && <Toast tone="exito" message={aviso} />}
    </main>
  );
}
