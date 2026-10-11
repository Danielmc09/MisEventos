import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { setupServer } from "msw/node";
import { MemoryRouter, useLocation } from "react-router-dom";
import App from "../App";
import { useSession } from "../stores/session";
import { API, usuario } from "../test/helpers";
import { responder } from "../test/msw";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useSession.getState().cerrarSesion();
});
afterAll(() => server.close());

function Ubicacion() {
  const { pathname, search } = useLocation();
  return <output aria-label="ubicación">{pathname + search}</output>;
}

const montar = (ruta: string) =>
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <App />
      <Ubicacion />
    </MemoryRouter>,
  );

const encabezado = () => screen.getByRole("banner");

test("sin sesión ofrece Iniciar sesión y Registrarse", async () => {
  montar("/");

  const nav = within(encabezado());
  expect(nav.getByRole("link", { name: "Iniciar sesión" })).toHaveAttribute("href", "/login");
  expect(nav.getByRole("link", { name: "Registrarse" })).toHaveAttribute("href", "/registro");
  expect(nav.queryByRole("button", { name: "Cerrar sesión" })).not.toBeInTheDocument();
});

test("con sesión muestra el email como enlace a /perfil y Cerrar sesión", async () => {
  useSession.getState().iniciarSesion(usuario, "token-abc");
  montar("/");

  const nav = within(encabezado());
  expect(nav.getByRole("link", { name: "ana@mail.com" })).toHaveAttribute("href", "/perfil");
  expect(nav.getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument();
  expect(nav.queryByRole("link", { name: "Iniciar sesión" })).not.toBeInTheDocument();
});

test("Cerrar sesión desde /perfil termina en /login sin next", async () => {
  server.use(
    http.post(`${API}/auth/logout`, () => new Response(null, { status: 204 })),
    http.get(`${API}/auth/me`, () => responder("/auth/me", "get", 200, usuario)),
  );
  useSession.getState().iniciarSesion(usuario, "token-abc");
  const user = userEvent.setup();
  montar("/perfil");
  await screen.findByRole("heading", { name: "Perfil" });

  await user.click(within(encabezado()).getByRole("button", { name: "Cerrar sesión" }));

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/login$/);
  expect(useSession.getState().accessToken).toBeNull();
});

test("/cambiar-contrasena es una ruta protegida", async () => {
  montar("/cambiar-contrasena");

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent("/login?next=%2Fcambiar-contrasena");
});

test("con sesión, /cambiar-contrasena muestra el formulario", async () => {
  useSession.getState().iniciarSesion(usuario, "token-abc");
  montar("/cambiar-contrasena");

  expect(await screen.findByLabelText("Contraseña actual")).toBeInTheDocument();
});
