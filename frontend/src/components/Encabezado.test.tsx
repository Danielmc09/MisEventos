import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { setupServer } from "msw/node";
import { MemoryRouter, useLocation } from "react-router-dom";
import App from "../App";
import { useSession } from "../stores/session";
import { API, usuario } from "../test/helpers";
import { responder } from "../test/msw";

const server = setupServer(
  http.get(`${API}/events`, () =>
    responder("/events", "get", 200, { items: [], total: 0, page: 1, page_size: 12, pages: 0 }),
  ),
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

const encabezado = () => screen.getByRole("banner");

test("sin sesión ofrece Iniciar sesión y Registrarse", async () => {
  montar("/");

  const nav = within(encabezado());
  expect(nav.getByRole("link", { name: "Iniciar sesión" })).toHaveAttribute("href", "/login");
  expect(nav.getByRole("link", { name: "Registrarse" })).toHaveAttribute("href", "/registro");
  expect(nav.queryByRole("button", { name: "Cerrar sesión" })).not.toBeInTheDocument();
});

test("con sesión muestra el nombre y no el email", () => {
  useSession
    .getState()
    .iniciarSesion({ ...usuario, full_name: "Oscar Organizador" }, "token-abc", 3600);
  montar("/");

  const nav = within(encabezado());
  expect(nav.getByRole("link", { name: "Oscar Organizador" })).toHaveAttribute("href", "/perfil");
  expect(nav.queryByText(usuario.email)).not.toBeInTheDocument();
});

test("un nombre largo se corta con «…» pero se lee completo en su título", () => {
  const largo = "Oscar Organizador Con Un Nombre Larguísimo De Verdad";
  useSession.getState().iniciarSesion({ ...usuario, full_name: largo }, "token-abc", 3600);
  montar("/");

  expect(within(encabezado()).getByRole("link", { name: largo })).toHaveAttribute("title", largo);
});

test.each([null, ""])("sin nombre (%j) muestra el email", (nombre) => {
  useSession.getState().iniciarSesion({ ...usuario, full_name: nombre }, "token-abc", 3600);
  montar("/");

  expect(within(encabezado()).getByRole("link", { name: usuario.email })).toHaveAttribute(
    "href",
    "/perfil",
  );
});

test("con sesión muestra el enlace a /perfil y Cerrar sesión", async () => {
  useSession.getState().iniciarSesion(usuario, "token-abc", 3600);
  montar("/");

  const nav = within(encabezado());
  expect(nav.getByRole("link", { name: "Ana" })).toHaveAttribute("href", "/perfil");
  expect(nav.getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument();
  expect(nav.queryByRole("link", { name: "Iniciar sesión" })).not.toBeInTheDocument();
});

const logout = {
  ok: () => http.post(`${API}/auth/logout`, () => new Response(null, { status: 204 })),
  red: () => http.post(`${API}/auth/logout`, () => Response.error()),
};

describe.each([
  ["con el logout correcto", logout.ok],
  ["con el logout fallando por red", logout.red],
])("Cerrar sesión desde /perfil %s", (_caso, manejador) => {
  describe.each([
    ["en el encabezado", () => within(encabezado()).getByRole("button", { name: "Cerrar sesión" })],
    [
      "en el perfil",
      () => within(screen.getByRole("main")).getByRole("button", { name: "Cerrar sesión" }),
    ],
  ])("%s", (_donde, boton) => {
    test("termina en /login limpio y con la sesión vacía", async () => {
      server.use(
        manejador(),
        http.get(`${API}/auth/me`, () => responder("/auth/me", "get", 200, usuario)),
      );
      useSession.getState().iniciarSesion(usuario, "token-abc", 3600);
      const user = userEvent.setup();
      montar("/perfil");
      await screen.findByRole("heading", { name: "Perfil" });

      await user.click(boton());

      expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
      expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/login$/);
      expect(useSession.getState().accessToken).toBeNull();
    });
  });
});

test("/cambiar-contrasena es una ruta protegida", async () => {
  montar("/cambiar-contrasena");

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent("/login?next=%2Fcambiar-contrasena");
});

test("con sesión, /cambiar-contrasena muestra el formulario", async () => {
  useSession.getState().iniciarSesion(usuario, "token-abc", 3600);
  montar("/cambiar-contrasena");

  expect(await screen.findByLabelText("Contraseña actual")).toBeInTheDocument();
});

test.each([
  ["un asistente con el permiso", { ...usuario, role: "ATTENDEE" as const }],
  ["un organizador con el permiso", { ...usuario, role: "ORGANIZER" as const }],
])("%s ve Crear evento hacia /eventos/nuevo", (_caso, quien) => {
  useSession.getState().iniciarSesion({ ...quien, permisos: ["evento:crear"] }, "token-abc", 3600);
  montar("/");

  expect(within(encabezado()).getByRole("link", { name: "Crear evento" })).toHaveAttribute(
    "href",
    "/eventos/nuevo",
  );
});

test.each([
  ["un organizador", "ORGANIZER" as const],
  ["un admin", "ADMIN" as const],
  ["un asistente", "ATTENDEE" as const],
])("%s sin el permiso evento:crear no ve Crear evento", (_caso, role) => {
  useSession.getState().iniciarSesion({ ...usuario, role, permisos: [] }, "token-abc", 3600);
  montar("/");

  expect(within(encabezado()).getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument();
  expect(
    within(encabezado()).queryByRole("link", { name: "Crear evento" }),
  ).not.toBeInTheDocument();
});

test("un anónimo no ve Crear evento", () => {
  montar("/");

  expect(
    within(encabezado()).queryByRole("link", { name: "Crear evento" }),
  ).not.toBeInTheDocument();
});

test("/eventos/nuevo es una ruta protegida", async () => {
  montar("/eventos/nuevo");

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent("/login?next=%2Feventos%2Fnuevo");
});

test("con sesión, /eventos/nuevo muestra la pantalla de nuevo evento", async () => {
  useSession.getState().iniciarSesion(usuario, "token-abc", 3600);
  montar("/eventos/nuevo");

  expect(await screen.findByRole("heading", { name: "Nuevo evento" })).toBeInTheDocument();
});

describe("en una pantalla angosta", () => {
  beforeEach(() =>
    vi.stubGlobal("matchMedia", (media: string) => ({
      matches: true,
      media,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  );
  afterEach(() => vi.unstubAllGlobals());

  test("con sesión deja el logo y un círculo con la inicial que abre el menú de la cuenta", async () => {
    useSession
      .getState()
      .iniciarSesion(
        { ...usuario, full_name: "Oscar Organizador", permisos: ["evento:crear"] },
        "token-abc",
        3600,
      );
    const user = userEvent.setup();
    montar("/");

    const nav = within(encabezado());
    expect(nav.getByRole("link", { name: "Mis Eventos" })).toBeInTheDocument();
    expect(nav.queryByRole("button", { name: "Cerrar sesión" })).not.toBeInTheDocument();
    const menu = nav.getByRole("button", { name: "Menú de la cuenta" });
    expect(menu).toHaveTextContent("O");

    await user.click(menu);

    expect(nav.getByRole("menuitem", { name: "Crear evento" })).toHaveAttribute(
      "href",
      "/eventos/nuevo",
    );
    expect(nav.getByRole("menuitem", { name: "Mi perfil" })).toHaveAttribute("href", "/perfil");
    // El nombre es el encabezado del menú, no un enlace.
    expect(nav.getByText("Oscar Organizador")).toBeInTheDocument();
    expect(nav.queryByRole("menuitem", { name: "Oscar Organizador" })).not.toBeInTheDocument();
    expect(nav.getByRole("menuitem", { name: "Cerrar sesión" })).toBeInTheDocument();
  });
});
