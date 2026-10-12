import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { AlertaError } from "../../components/ui/AlertaError";
import { Button } from "../../components/ui/Button";
import { Enlace } from "../../components/ui/Enlace";
import { Formulario, GrupoCampos } from "../../components/ui/Formulario";
import { Input } from "../../components/ui/Input";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";
import { Tarjeta } from "../../components/ui/Tarjeta";
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
    <Pagina ancho="angosto">
      <TituloPagina>Iniciar sesión</TituloPagina>
      <Tarjeta as="div">
        <Formulario onSubmit={enviar}>
          <GrupoCampos>
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
          </GrupoCampos>
          {error?.general && <AlertaError title={error.general} />}
          <Button type="submit" loading={enviando}>
            Iniciar sesión
          </Button>
        </Formulario>
        <Enlace to={`/registro${conservarNext(next)}`}>¿No tenés cuenta? Registrate</Enlace>
      </Tarjeta>
    </Pagina>
  );
}
