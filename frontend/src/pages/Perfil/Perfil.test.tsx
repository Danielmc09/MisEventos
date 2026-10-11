import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { useSession } from "../../stores/session";
import { API, montar, usuario } from "../../test/helpers";
import Login from "../Login/Login";
import Perfil from "./Perfil";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => useSession.getState().iniciarSesion(usuario, "token-abc", 3600));
afterEach(() => {
  server.resetHandlers();
  useSession.getState().cerrarSesion();
});
afterAll(() => server.close());

const montarPerfil = () =>
  montar("/perfil", [
    ["/perfil", <Perfil />],
    ["/login", <Login />],
  ]);

test("muestra el email, el nombre y el rol, y un enlace a cambiar la contraseña", () => {
  montarPerfil();

  expect(screen.getByText("ana@mail.com")).toBeInTheDocument();
  expect(screen.getByText("Ana")).toBeInTheDocument();
  expect(screen.getByText("Asistente")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Cambiar contraseña" })).toHaveAttribute(
    "href",
    "/cambiar-contrasena",
  );
});

test('"Cerrar sesión" llama a logout, vacía la sesión y lleva a /login', async () => {
  let autorizacion: string | null = null;
  server.use(
    http.post(`${API}/auth/logout`, ({ request }) => {
      autorizacion = request.headers.get("Authorization");
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const user = userEvent.setup();
  montarPerfil();

  await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(autorizacion).toBe("Bearer token-abc");
  expect(useSession.getState().accessToken).toBeNull();
  expect(useSession.getState().user).toBeNull();
});

test("si el logout falla por red, igual vacía la sesión", async () => {
  server.use(http.post(`${API}/auth/logout`, () => HttpResponse.error()));
  const user = userEvent.setup();
  montarPerfil();

  await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(useSession.getState().accessToken).toBeNull();
});

test("el aviso de contraseña cambiada se muestra una vez: se limpia el state", async () => {
  montar({ pathname: "/perfil", state: { aviso: "Tu contraseña se cambió" } }, [
    ["/perfil", <Perfil />],
  ]);

  expect(screen.getByText("Tu contraseña se cambió")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText("estado")).toHaveTextContent("null"));
});
