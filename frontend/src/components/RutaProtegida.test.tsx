import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import App from "../App";
import { useSession } from "../stores/session";
import { usuario } from "../test/helpers";

afterEach(() => useSession.getState().cerrarSesion());

function Ubicacion() {
  const { pathname, search } = useLocation();
  return <output aria-label="ubicación">{pathname + search}</output>;
}

const abrirPerfil = () =>
  render(
    <MemoryRouter initialEntries={["/perfil"]}>
      <App />
      <Ubicacion />
    </MemoryRouter>,
  );

test("con la sesión vencida, /perfil lleva a /login?next y el encabezado no muestra al usuario", async () => {
  useSession.setState({ user: usuario, accessToken: "token-viejo", expiresAt: Date.now() - 1000 });

  abrirPerfil();

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/login\?next=%2Fperfil$/);
  expect(screen.queryByRole("link", { name: usuario.email })).not.toBeInTheDocument();
  expect(useSession.getState().accessToken).toBeNull();
});

test("una sesión persistida sin vencimiento cuenta como vencida", async () => {
  useSession.setState({ user: usuario, accessToken: "token-viejo", expiresAt: null });

  abrirPerfil();

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
});

test("con la sesión vigente se muestra /perfil", async () => {
  useSession.setState({ user: usuario, accessToken: "token", expiresAt: Date.now() + 60_000 });

  abrirPerfil();

  expect(await screen.findByRole("heading", { name: "Perfil" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: usuario.email })).toBeInTheDocument();
});
