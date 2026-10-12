import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { AlertaError } from "../../components/ui/AlertaError";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useAvisos } from "../../components/ui/Avisos";
import { errorDeFormulario, type ErrorDeFormulario } from "../../lib/errores";
import { useSession } from "../../stores/session";

export default function CambiarContrasena() {
  const navigate = useNavigate();
  const avisar = useAvisos();
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<ErrorDeFormulario | null>(null);

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const datos = new FormData(e.currentTarget);
    if (datos.get("new_password") !== datos.get("confirmacion")) {
      setError({ campos: { confirmacion: "Las contraseñas no coinciden" }, general: null });
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      const { access_token, expires_in } = await api<components["schemas"]["TokenAcceso"]>(
        "/auth/me/password",
        {
          method: "PATCH",
          body: JSON.stringify({
            current_password: datos.get("current_password"),
            new_password: datos.get("new_password"),
          }),
        },
      );
      const { user } = useSession.getState();
      if (user) useSession.getState().iniciarSesion(user, access_token, expires_in);
      avisar({ message: "Cambiaste tu contraseña", tone: "exito" });
      navigate("/perfil");
    } catch (err) {
      const fallo = errorDeFormulario(err);
      setError(fallo);
      setEnviando(false);
    }
  }

  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-2xl font-bold">Cambiar contraseña</h1>
      <form onSubmit={enviar} className="mt-4 flex flex-col gap-4">
        <Input
          label="Contraseña actual"
          name="current_password"
          type="password"
          autoComplete="current-password"
          required
          error={error?.campos.current_password}
        />
        <Input
          label="Contraseña nueva"
          name="new_password"
          type="password"
          autoComplete="new-password"
          required
          error={error?.campos.new_password}
        />
        <Input
          label="Confirmá la contraseña nueva"
          name="confirmacion"
          type="password"
          autoComplete="new-password"
          required
          error={error?.campos.confirmacion}
        />
        {error?.general && <AlertaError title={error.general} />}
        <Button type="submit" loading={enviando}>
          Cambiar contraseña
        </Button>
      </form>
    </main>
  );
}
