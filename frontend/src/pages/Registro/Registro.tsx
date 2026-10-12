import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useAvisos } from "../../components/ui/Avisos";
import { errorDeFormulario, type ErrorDeFormulario } from "../../lib/errores";
import { conservarNext } from "../../lib/next";

export default function Registro() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const destino = conservarNext(params.get("next"));
  const avisar = useAvisos();
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<ErrorDeFormulario | null>(null);

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const datos = new FormData(e.currentTarget);
    setEnviando(true);
    setError(null);
    try {
      const { message } = await api<components["schemas"]["Mensaje"]>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: datos.get("email"),
          password: datos.get("password"),
          full_name: datos.get("full_name") || null,
        }),
      });
      avisar({ message, tone: "exito" });
      navigate(`/login${destino}`);
    } catch (err) {
      const fallo = errorDeFormulario(err);
      setError(fallo);
      if (fallo.general) avisar({ message: fallo.general, tone: "error" });
      setEnviando(false);
    }
  }

  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-2xl font-bold">Crear cuenta</h1>
      <form onSubmit={enviar} className="mt-4 flex flex-col gap-4">
        <Input
          label="Correo electrónico"
          name="email"
          type="email"
          autoComplete="email"
          required
          error={error?.campos.email}
        />
        <Input
          label="Contraseña"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          error={error?.campos.password}
        />
        <Input
          label="Nombre (opcional)"
          name="full_name"
          autoComplete="name"
          error={error?.campos.full_name}
        />
        <Button type="submit" loading={enviando}>
          Crear cuenta
        </Button>
      </form>
      <p className="mt-4 text-sm">
        <Link to={`/login${destino}`} className="text-indigo-700 underline">
          ¿Ya tenés cuenta? Iniciá sesión
        </Link>
      </p>
    </main>
  );
}
