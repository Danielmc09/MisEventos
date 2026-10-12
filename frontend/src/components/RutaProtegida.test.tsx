import { render, screen } from "@testing-library/react";
import { http } from "msw";
import { setupServer } from "msw/node";
import { MemoryRouter, useLocation } from "react-router-dom";
import App from "../App";
import { useSession } from "../stores/session";
import { API, usuario } from "../test/helpers";
import { responder } from "../test/msw";

const server = setupServer(
  http.get(`${API}/auth/me`, () => responder("/auth/me", "get", 200, usuario)),
  http.get(`${API}/me/registrations`, () =>
    responder("/me/registrations", "get", 200, {
      items: [],
      total: 0,
      page: 1,
      page_size: 12,
      pages: 0,
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => useSession.getState().cerrarSesion());
afterAll(() => server.close());

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
  expect(screen.getByRole("button", { name: "Menú de la cuenta" })).toBeInTheDocument();
});
