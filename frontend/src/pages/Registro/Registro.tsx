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
      setEnviando(false);
    }
  }

  return (
    <Pagina ancho="angosto">
      <TituloPagina>Crear cuenta</TituloPagina>
      <Tarjeta as="div">
        <Formulario onSubmit={enviar}>
          <GrupoCampos>
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
          </GrupoCampos>
          {error?.general && <AlertaError title={error.general} />}
          <Button type="submit" loading={enviando}>
            Crear cuenta
          </Button>
        </Formulario>
        <Enlace to={`/login${destino}`}>¿Ya tenés cuenta? Iniciá sesión</Enlace>
      </Tarjeta>
    </Pagina>
  );
}
