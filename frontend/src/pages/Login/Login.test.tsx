import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http } from "msw";
import { setupServer } from "msw/node";
import { useSession } from "../../stores/session";
import { API, montar, usuario } from "../../test/helpers";
import { responder } from "../../test/msw";
import Registro from "../Registro/Registro";
import Login from "./Login";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useSession.getState().cerrarSesion();
});
afterAll(() => server.close());

const rutas: [string, React.ReactNode][] = [
  ["/login", <Login />],
  ["/registro", <Registro />],
  ["/eventos/:id", <h1>Evento</h1>],
  ["/", <h1>Inicio de prueba</h1>],
];

const clave = crypto.randomUUID();

const loginOk = () =>
  server.use(
    http.post(`${API}/auth/login`, () =>
      responder("/auth/login", "post", 200, {
        access_token: "token-abc",
        token_type: "bearer",
        expires_in: 3600,
      }),
    ),
    http.get(`${API}/auth/me`, () => responder("/auth/me", "get", 200, usuario)),
  );

async function ingresar(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Correo electrónico"), "ana@mail.com");
  await user.type(screen.getByLabelText("Contraseña"), clave);
  await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));
}

test("los campos del formulario tienen label", () => {
  montar("/login", rutas);

  expect(screen.getByLabelText("Correo electrónico")).toBeInTheDocument();
  expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
});

test("un login incorrecto muestra el title del problem+json", async () => {
  server.use(
    http.post(`${API}/auth/login`, () =>
      responder("/auth/login", "post", 401, {
        type: "invalid-credentials",
        title: "El correo o la contraseña no son correctos",
        status: 401,
        trace_id: "t-1",
      }),
    ),
  );
  const user = userEvent.setup();
  montar("/login", rutas);

  await ingresar(user);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "El correo o la contraseña no son correctos",
  );
  expect(useSession.getState().accessToken).toBeNull();
  expect(screen.getByRole("button", { name: /iniciar sesión/i })).toBeEnabled();
});

test("mientras se envía el botón queda deshabilitado", async () => {
  server.use(
    http.post(`${API}/auth/login`, async () => {
      await delay(100);
      return responder("/auth/login", "post", 200, {
        access_token: "token-abc",
        token_type: "bearer",
        expires_in: 3600,
      });
    }),
    http.get(`${API}/auth/me`, () => responder("/auth/me", "get", 200, usuario)),
  );
  const user = userEvent.setup();
  montar("/login", rutas);

  await ingresar(user);

  expect(screen.getByRole("button", { name: /iniciar sesión/i })).toBeDisabled();
  await waitFor(() => expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/$/));
});

test("un login exitoso guarda el usuario y el token, y vuelve a la ruta de origen", async () => {
  let formulario: URLSearchParams | undefined;
  let autorizacion: string | null = null;
  server.use(
    http.post(`${API}/auth/login`, async ({ request }) => {
      formulario = new URLSearchParams(await request.text());
      return responder("/auth/login", "post", 200, {
        access_token: "token-abc",
        token_type: "bearer",
        expires_in: 3600,
      });
    }),
    http.get(`${API}/auth/me`, ({ request }) => {
      autorizacion = request.headers.get("Authorization");
      return responder("/auth/me", "get", 200, usuario);
    }),
  );
  const user = userEvent.setup();
  montar("/login?next=%2Feventos%2Fabc", rutas);

  await ingresar(user);

  expect(await screen.findByRole("heading", { name: "Evento" })).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/eventos\/abc$/);
  expect(useSession.getState().user).toEqual(usuario);
  expect(useSession.getState().accessToken).toBe("token-abc");
  expect(formulario?.get("username")).toBe("ana@mail.com");
  expect(formulario?.get("password")).toBe(clave);
  expect(autorizacion).toBe("Bearer token-abc");
});

test.each(["https://otro-sitio.com", "//otro-sitio.com", "javascript:alert(1)"])(
  "next=%s se ignora y después del login va a /",
  async (next) => {
    loginOk();
    const user = userEvent.setup();
    montar(`/login?next=${encodeURIComponent(next)}`, rutas);

    await ingresar(user);

    expect(await screen.findByRole("heading", { name: "Inicio de prueba" })).toBeInTheDocument();
    expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/$/);
  },
);

test("el enlace a registrarse conserva next", () => {
  montar("/login?next=%2Feventos%2Fabc", rutas);

  expect(screen.getByRole("link", { name: "¿No tenés cuenta? Registrate" })).toHaveAttribute(
    "href",
    "/registro?next=%2Feventos%2Fabc",
  );
});

test("registro, login y vuelta al next original", async () => {
  server.use(
    http.post(`${API}/auth/register`, () =>
      responder("/auth/register", "post", 201, { message: "Cuenta creada" }),
    ),
  );
  loginOk();
  const user = userEvent.setup();
  montar("/registro?next=%2Feventos%2Fabc", rutas);

  await user.type(screen.getByLabelText("Correo electrónico"), "ana@mail.com");
  await user.type(screen.getByLabelText("Contraseña"), clave);
  await user.click(screen.getByRole("button", { name: /crear cuenta/i }));
  await screen.findByRole("heading", { name: "Iniciar sesión" });
  await ingresar(user);

  expect(await screen.findByRole("heading", { name: "Evento" })).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/eventos\/abc$/);
});

const organizador = {
  ...usuario,
  id: "11111111-2222-4333-8444-555555555555",
  email: "org@mail.com",
  role: "ORGANIZER" as const,
  permisos: ["evento:crear" as const],
};

test("con la sesión de otro usuario en el store, el login deja el usuario y el token de la cuenta nueva", async () => {
  server.use(
    http.post(`${API}/auth/login`, () =>
      responder("/auth/login", "post", 200, {
        access_token: "token-organizador",
        token_type: "bearer",
        expires_in: 3600,
      }),
    ),
    http.get(`${API}/auth/me`, ({ request }) =>
      responder(
        "/auth/me",
        "get",
        200,
        request.headers.get("Authorization") === "Bearer token-organizador" ? organizador : usuario,
      ),
    ),
  );
  useSession.getState().iniciarSesion(usuario, "token-asistente", 3600);
  const user = userEvent.setup();
  montar("/login", rutas);

  await ingresar(user);

  await screen.findByRole("heading", { name: "Inicio de prueba" });
  expect(useSession.getState().user).toEqual(organizador);
  expect(useSession.getState().accessToken).toBe("token-organizador");
});

test("con un token vencido en el store, el login con credenciales correctas funciona a la primera", async () => {
  server.use(
    http.post(`${API}/auth/login`, () =>
      responder("/auth/login", "post", 200, {
        access_token: "token-nuevo",
        token_type: "bearer",
        expires_in: 3600,
      }),
    ),
    http.get(`${API}/auth/me`, ({ request }) =>
      request.headers.get("Authorization") === "Bearer token-nuevo"
        ? responder("/auth/me", "get", 200, usuario)
        : responder("/auth/me", "get", 401, {
            type: "unauthorized",
            title: "Sesión inválida",
            status: 401,
            trace_id: "t-1",
          }),
    ),
  );
  useSession.getState().iniciarSesion(usuario, "token-vencido", 3600);
  const user = userEvent.setup();
  montar("/login", rutas);

  await ingresar(user);

  await screen.findByRole("heading", { name: "Inicio de prueba" });
  expect(useSession.getState().accessToken).toBe("token-nuevo");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test.each(["//evil.com", "https://evil.com", "javascript:alert(1)"])(
  "el enlace a registrarse no lleva un next hostil (%s)",
  (next) => {
    montar(`/login?next=${encodeURIComponent(next)}`, rutas);

    expect(screen.getByRole("link", { name: "¿No tenés cuenta? Registrate" })).toHaveAttribute(
      "href",
      "/registro",
    );
  },
);

const conAviso = {
  pathname: "/login",
  search: "?next=%2Feventos%2Fabc",
  state: { aviso: "Registro recibido" },
};

test("el aviso de registro se muestra una vez: se limpia el state y el next sigue en la URL", async () => {
  montar(conAviso, rutas);

  expect(screen.getByText("Registro recibido")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText("estado")).toHaveTextContent("null"));
  expect(screen.getByLabelText("ubicación")).toHaveTextContent("/login?next=%2Feventos%2Fabc");
});

test("tras un login fallido ya no está el aviso de registro y sí el error", async () => {
  server.use(
    http.post(`${API}/auth/login`, () =>
      responder("/auth/login", "post", 401, {
        type: "invalid-credentials",
        title: "El correo o la contraseña no son correctos",
        status: 401,
        trace_id: "t-1",
      }),
    ),
  );
  const user = userEvent.setup();
  montar(conAviso, rutas);

  await ingresar(user);

  expect(await screen.findByRole("alert")).toHaveTextContent("no son correctos");
  expect(screen.queryByText("Registro recibido")).not.toBeInTheDocument();
});
