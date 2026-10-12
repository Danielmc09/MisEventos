import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { AlertaError } from "../../components/ui/AlertaError";
import { Button } from "../../components/ui/Button";
import { Formulario, GrupoCampos } from "../../components/ui/Formulario";
import { Input } from "../../components/ui/Input";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";
import { Tarjeta } from "../../components/ui/Tarjeta";
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
    <Pagina ancho="angosto">
      <TituloPagina>Cambiar contraseña</TituloPagina>
      <Tarjeta as="div">
        <Formulario onSubmit={enviar}>
          <GrupoCampos>
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
          </GrupoCampos>
          {error?.general && <AlertaError title={error.general} />}
          <Button type="submit" loading={enviando}>
            Cambiar contraseña
          </Button>
        </Formulario>
      </Tarjeta>
    </Pagina>
  );
}
