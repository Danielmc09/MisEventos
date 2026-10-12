import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http } from "msw";
import { setupServer } from "msw/node";
import { responder } from "../../test/msw";
import { API, montar } from "../../test/helpers";
import Login from "../Login/Login";
import Registro from "./Registro";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const montarRegistro = (ruta = "/registro") =>
  montar(ruta, [
    ["/registro", <Registro />],
    ["/login", <Login />],
  ]);

const clave = crypto.randomUUID();

async function completar(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Correo electrónico"), "ana@mail.com");
  await user.type(screen.getByLabelText("Contraseña"), clave);
  await user.type(screen.getByLabelText("Nombre (opcional)"), "Ana");
}

test("los campos del formulario tienen label", () => {
  montarRegistro();

  expect(screen.getByLabelText("Correo electrónico")).toBeInTheDocument();
  expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
  expect(screen.getByLabelText("Nombre (opcional)")).toBeInTheDocument();
});

test("un 422 se muestra en el campo, asociado con aria-describedby", async () => {
  server.use(
    http.post(`${API}/auth/register`, () =>
      responder("/auth/register", "post", 422, {
        type: "validation-error",
        title: "Los datos enviados no son válidos",
        status: 422,
        trace_id: "t-1",
        errors: [{ field: "email", message: "El correo no es válido" }],
      }),
    ),
  );
  const user = userEvent.setup();
  montarRegistro();

  await completar(user);
  await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

  expect(await screen.findByLabelText("Correo electrónico")).toHaveAccessibleDescription(
    "El correo no es válido",
  );
});

test("un error sin campo muestra el title del problem+json", async () => {
  server.use(
    http.post(`${API}/auth/register`, () =>
      responder("/auth/register", "post", 422, {
        type: "validation-error",
        title: "Los datos enviados no son válidos",
        status: 422,
        trace_id: "t-1",
      }),
    ),
  );
  const user = userEvent.setup();
  montarRegistro();

  await completar(user);
  await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Los datos enviados no son válidos");
});

test("mientras se envía el botón queda deshabilitado", async () => {
  server.use(
    http.post(`${API}/auth/register`, async () => {
      await delay(100);
      return responder("/auth/register", "post", 201, { message: "Listo" });
    }),
  );
  const user = userEvent.setup();
  montarRegistro();

  await completar(user);
  await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

  expect(screen.getByRole("button", { name: /crear cuenta/i })).toBeDisabled();
  await waitFor(() => expect(screen.getByLabelText("ubicación")).toHaveTextContent("/login"));
});

test("al registrarse muestra el mensaje del backend y lleva a /login conservando next", async () => {
  let cuerpo: unknown;
  server.use(
    http.post(`${API}/auth/register`, async ({ request }) => {
      cuerpo = await request.json();
      return responder("/auth/register", "post", 201, {
        message: "Si el correo es válido, te enviamos las instrucciones",
      });
    }),
  );
  const user = userEvent.setup();
  montarRegistro("/registro?next=%2Feventos%2Fabc");

  await completar(user);
  await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(
    screen.getByText("Si el correo es válido, te enviamos las instrucciones"),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent("/login?next=%2Feventos%2Fabc");
  expect(cuerpo).toEqual({ email: "ana@mail.com", password: clave, full_name: "Ana" });
});

test("el enlace a iniciar sesión conserva next", () => {
  montarRegistro("/registro?next=%2Feventos%2Fabc");

  expect(screen.getByRole("link", { name: "¿Ya tenés cuenta? Iniciá sesión" })).toHaveAttribute(
    "href",
    "/login?next=%2Feventos%2Fabc",
  );
});

test.each(["//evil.com", "https://evil.com", "javascript:alert(1)"])(
  "el enlace a iniciar sesión no lleva un next hostil (%s)",
  (next) => {
    montarRegistro(`/registro?next=${encodeURIComponent(next)}`);

    expect(screen.getByRole("link", { name: "¿Ya tenés cuenta? Iniciá sesión" })).toHaveAttribute(
      "href",
      "/login",
    );
  },
);

test("al registrarse con un next hostil, va a /login sin next", async () => {
  server.use(
    http.post(`${API}/auth/register`, () =>
      responder("/auth/register", "post", 201, { message: "Listo" }),
    ),
  );
  const user = userEvent.setup();
  montarRegistro(`/registro?next=${encodeURIComponent("//evil.com")}`);

  await completar(user);
  await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

  await screen.findByRole("heading", { name: "Iniciar sesión" });
  expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/login$/);
});

test("el error general queda en el formulario pasados los 4 s y se borra al reenviar con éxito", async () => {
  server.use(
    http.post(`${API}/auth/register`, () =>
      responder("/auth/register", "post", 422, {
        type: "validation-error",
        title: "Los datos enviados no son válidos",
        status: 422,
        trace_id: "t-1",
      }),
    ),
  );
  const user = userEvent.setup();
  montarRegistro();
  await completar(user);
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  try {
    fireEvent.click(screen.getByRole("button", { name: /crear cuenta/i }));
    await act(async () => {
      for (let i = 0; i < 50 && !screen.queryByRole("alert"); i++)
        await new Promise((r) => setImmediate(r));
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Los datos enviados no son válidos");
    act(() => vi.advanceTimersByTime(5000));

    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent("Los datos enviados no son válidos");
    expect(alerta.closest("form")).not.toBeNull();
  } finally {
    vi.useRealTimers();
  }

  server.use(
    http.post(`${API}/auth/register`, () =>
      responder("/auth/register", "post", 201, { message: "Listo" }),
    ),
  );
  await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

  await screen.findByRole("heading", { name: "Iniciar sesión" });
  expect(screen.queryByText("Los datos enviados no son válidos")).not.toBeInTheDocument();
});
