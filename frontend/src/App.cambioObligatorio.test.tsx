import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { setupServer } from "msw/node";
import { MemoryRouter, useLocation } from "react-router-dom";
import App from "./App";
import type { components } from "./api/schema";
import { useSession } from "./stores/session";
import { API, usuario } from "./test/helpers";
import { responder } from "./test/msw";

type Perfil = components["schemas"]["PerfilConPermisos"];

const pendiente: Perfil = { ...usuario, must_change_password: true };
const clave = crypto.randomUUID();
const MENSAJE = "Tenés que cambiar tu contraseña temporal para continuar";

const server = setupServer(
  http.get(`${API}/auth/me`, () => responder("/auth/me", "get", 200, pendiente)),
  http.get(`${API}/events`, () =>
    responder("/events", "get", 200, { items: [], total: 0, page: 1, page_size: 12, pages: 0 }),
  ),
  http.post(`${API}/auth/logout`, () => new Response(null, { status: 204 })),
);

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

const ubicacion = () => screen.getByLabelText("ubicación");

test("después del login, con contraseña temporal, va directo a /cambiar-contrasena con el mensaje", async () => {
  server.use(
    http.post(`${API}/auth/login`, () =>
      responder("/auth/login", "post", 200, {
        access_token: "token-temporal",
        token_type: "bearer",
        expires_in: 3600,
      }),
    ),
  );
  const user = userEvent.setup();
  montar("/login");

  await user.type(await screen.findByLabelText("Correo electrónico"), pendiente.email);
  await user.type(screen.getByLabelText("Contraseña"), clave);
  await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));

  expect(await screen.findByRole("heading", { name: "Cambiar contraseña" })).toBeInTheDocument();
  expect(ubicacion()).toHaveTextContent(/^\/cambiar-contrasena$/);
  expect(screen.getByRole("status")).toHaveTextContent(MENSAJE);
});

test.each(["/", "/perfil", "/eventos/abc"])(
  "con la contraseña temporal pendiente, %s lo devuelve a /cambiar-contrasena",
  async (ruta) => {
    useSession.getState().iniciarSesion(pendiente, "token-temporal", 3600);
    montar(ruta);

    expect(await screen.findByRole("heading", { name: "Cambiar contraseña" })).toBeInTheDocument();
    expect(ubicacion()).toHaveTextContent(/^\/cambiar-contrasena$/);
    expect(screen.getByRole("status")).toHaveTextContent(MENSAJE);
  },
);

test("sin contraseña temporal pendiente, /cambiar-contrasena no muestra el mensaje", async () => {
  server.use(http.get(`${API}/auth/me`, () => responder("/auth/me", "get", 200, usuario)));
  useSession.getState().iniciarSesion(usuario, "token-abc", 3600);
  montar("/cambiar-contrasena");

  await screen.findByRole("heading", { name: "Cambiar contraseña" });
  expect(screen.queryByText(MENSAJE)).not.toBeInTheDocument();
});

test("con la contraseña temporal pendiente, el menú de la cuenta y Cerrar sesión funcionan", async () => {
  useSession.getState().iniciarSesion(pendiente, "token-temporal", 3600);
  const user = userEvent.setup();
  montar("/cambiar-contrasena");

  await user.click(await screen.findByRole("button", { name: "Menú de la cuenta" }));
  await user.click(screen.getByRole("menuitem", { name: "Cerrar sesión" }));

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(ubicacion()).toHaveTextContent(/^\/login$/);
  expect(useSession.getState().accessToken).toBeNull();
});
