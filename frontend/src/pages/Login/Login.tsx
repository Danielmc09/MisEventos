import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { AlertaError } from "../../components/ui/AlertaError";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { errorDeFormulario, type ErrorDeFormulario } from "../../lib/errores";
import { conservarNext, rutaSegura } from "../../lib/next";
import { useSession } from "../../stores/session";

export default function Login() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<ErrorDeFormulario | null>(null);

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const datos = new FormData(e.currentTarget);
    setEnviando(true);
    setError(null);
    try {
      const { access_token, expires_in } = await api<components["schemas"]["TokenAcceso"]>(
        "/auth/login",
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            username: String(datos.get("username")),
            password: String(datos.get("password")),
          }),
        },
      );
      const user = await api<components["schemas"]["PerfilConPermisos"]>("/auth/me", {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      useSession.getState().iniciarSesion(user, access_token, expires_in);
      navigate(rutaSegura(next), { replace: true });
    } catch (err) {
      const fallo = errorDeFormulario(err);
      setError(fallo);
      setEnviando(false);
    }
  }

  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-2xl font-bold">Iniciar sesión</h1>
      <form onSubmit={enviar} className="mt-4 flex flex-col gap-4">
        <Input
          label="Correo electrónico"
          name="username"
          type="email"
          autoComplete="email"
          required
          error={error?.campos.username}
        />
        <Input
          label="Contraseña"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          error={error?.campos.password}
        />
        {error?.general && <AlertaError title={error.general} />}
        <Button type="submit" loading={enviando}>
          Iniciar sesión
        </Button>
      </form>
      <p className="mt-4 text-sm">
        <Link to={`/registro${conservarNext(next)}`} className="text-indigo-700 underline">
          ¿No tenés cuenta? Registrate
        </Link>
      </p>
    </main>
  );
}
