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

test("sin sesión ofrece Ingresar y Registrarse, sin el menú Entrar", () => {
  montar("/");

  const nav = within(encabezado());
  expect(nav.getByRole("link", { name: "Ingresar" })).toHaveAttribute("href", "/login");
  expect(nav.getByRole("link", { name: "Registrarse" })).toHaveAttribute("href", "/registro");
  expect(nav.queryByRole("button", { name: "Menú de la cuenta" })).not.toBeInTheDocument();
  expect(nav.queryByText("Entrar")).not.toBeInTheDocument();
  expect(nav.queryByRole("link", { name: "Iniciar sesión" })).not.toBeInTheDocument();
});

test("Registrarse se oculta por debajo de 375 px y Ingresar siempre se ve", () => {
  montar("/");

  const nav = within(encabezado());
  expect(nav.getByRole("link", { name: "Registrarse" })).toHaveClass("hidden", "xs:inline-flex");
  expect(nav.getByRole("link", { name: "Ingresar" })).not.toHaveClass("hidden");
});

const abrirCuenta = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(within(encabezado()).getByRole("button", { name: "Menú de la cuenta" }));
  return within(encabezado());
};

test("con sesión deja el logo y un círculo con la inicial; el nombre y el email no se ven hasta abrir el menú", () => {
  useSession
    .getState()
    .iniciarSesion({ ...usuario, full_name: "Oscar Organizador" }, "token-abc", 3600);
  montar("/");

  const nav = within(encabezado());
  expect(nav.getByRole("link", { name: "Mis Eventos" })).toBeInTheDocument();
  expect(nav.getByRole("button", { name: "Menú de la cuenta" })).toHaveTextContent("O");
  expect(nav.queryByText("Oscar Organizador")).not.toBeInTheDocument();
  expect(nav.queryByText(usuario.email)).not.toBeInTheDocument();
  expect(nav.queryByRole("link", { name: "Oscar Organizador" })).not.toBeInTheDocument();
  expect(nav.queryByRole("button", { name: "Cerrar sesión" })).not.toBeInTheDocument();
  expect(nav.queryByRole("link", { name: "Iniciar sesión" })).not.toBeInTheDocument();
});

test("el menú de la cuenta tiene el nombre y el email como encabezado, y las tres opciones", async () => {
  useSession
    .getState()
    .iniciarSesion({ ...usuario, full_name: "Oscar Organizador" }, "token-abc", 3600);
  const user = userEvent.setup();
  montar("/");

  const nav = await abrirCuenta(user);

  expect(nav.getByText("Oscar Organizador")).toBeInTheDocument();
  expect(nav.getByText(usuario.email)).toBeInTheDocument();
  expect(nav.queryByRole("menuitem", { name: /Oscar Organizador/ })).not.toBeInTheDocument();
  expect(nav.getAllByRole("menuitem").map((i) => i.textContent)).toEqual([
    "Mi perfil",
    "Cerrar sesión",
  ]);
  expect(nav.queryByRole("menuitem", { name: "Cambiar contraseña" })).not.toBeInTheDocument();
  expect(nav.getByRole("menuitem", { name: "Mi perfil" })).toHaveAttribute("href", "/perfil");
  expect(nav.getByRole("separator")).toBeInTheDocument();
});

test.each([null, ""])(
  "sin nombre (%j) el círculo lleva la inicial del email y el encabezado el email",
  async (nombre) => {
    useSession.getState().iniciarSesion({ ...usuario, full_name: nombre }, "token-abc", 3600);
    const user = userEvent.setup();
    montar("/");

    const nav = await abrirCuenta(user);

    expect(nav.getByRole("button", { name: "Menú de la cuenta" })).toHaveTextContent("A");
    expect(nav.getAllByText(usuario.email)).toHaveLength(1);
  },
);

test("Escape cierra el menú de la cuenta y devuelve el foco al círculo", async () => {
  useSession.getState().iniciarSesion(usuario, "token-abc", 3600);
  const user = userEvent.setup();
  montar("/");

  const nav = await abrirCuenta(user);
  expect(nav.getByRole("menu")).toBeInTheDocument();
  await user.keyboard("{Escape}");

  expect(nav.queryByRole("menu")).not.toBeInTheDocument();
  expect(nav.getByRole("button", { name: "Menú de la cuenta" })).toHaveFocus();
});

const logout = {
  ok: () => http.post(`${API}/auth/logout`, () => new Response(null, { status: 204 })),
  red: () => http.post(`${API}/auth/logout`, () => Response.error()),
};

describe.each([
  ["con el logout correcto", logout.ok],
  ["con el logout fallando por red", logout.red],
])("Cerrar sesión desde el menú de la cuenta %s", (_caso, manejador) => {
  test("termina en /login limpio y con la sesión vacía", async () => {
    server.use(
      manejador(),
      http.get(`${API}/auth/me`, () => responder("/auth/me", "get", 200, usuario)),
    );
    useSession.getState().iniciarSesion(usuario, "token-abc", 3600);
    const user = userEvent.setup();
    montar("/perfil");
    await screen.findByRole("heading", { name: "Perfil" });

    const nav = await abrirCuenta(user);
    await user.click(nav.getByRole("menuitem", { name: "Cerrar sesión" }));

    expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
    expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/login$/);
    expect(useSession.getState().accessToken).toBeNull();
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

  expect(
    within(encabezado()).getByRole("button", { name: "Menú de la cuenta" }),
  ).toBeInTheDocument();
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

  test("con sesión es igual que en escritorio: logo, Crear evento y el círculo", () => {
    useSession
      .getState()
      .iniciarSesion(
        { ...usuario, full_name: "Oscar Organizador", permisos: ["evento:crear"] },
        "token-abc",
        3600,
      );
    montar("/");

    const nav = within(encabezado());
    expect(nav.getByRole("link", { name: "Mis Eventos" })).toBeInTheDocument();
    expect(nav.getByRole("link", { name: "Crear evento" })).toHaveAttribute(
      "href",
      "/eventos/nuevo",
    );
    expect(nav.getByRole("button", { name: "Menú de la cuenta" })).toHaveTextContent("O");
  });
});
