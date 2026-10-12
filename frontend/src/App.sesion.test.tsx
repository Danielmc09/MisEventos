import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { MemoryRouter, useLocation } from "react-router-dom";
import App from "./App";
import type { components } from "./api/schema";
import { useSession } from "./stores/session";
import { API, usuario } from "./test/helpers";
import { responder } from "./test/msw";

type Perfil = components["schemas"]["PerfilConPermisos"];

const organizador: Perfil = { ...usuario, role: "ORGANIZER", permisos: ["evento:crear"] };
const asistente: Perfil = { ...usuario, role: "ATTENDEE", permisos: [] };

let llamadasMe = 0;
let respuestaMe: () => Response | Promise<Response>;

const server = setupServer(
  http.get(`${API}/auth/me`, () => {
    llamadasMe += 1;
    return respuestaMe();
  }),
  http.get(`${API}/events`, () =>
    responder("/events", "get", 200, { items: [], total: 0, page: 1, page_size: 12, pages: 0 }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  llamadasMe = 0;
  useSession.getState().iniciarSesion(organizador, "token-abc", 3600);
});
afterEach(() => {
  cleanup();
  useSession.getState().cerrarSesion();
  localStorage.clear();
});
afterAll(() => server.close());

function Ubicacion() {
  const { pathname, search } = useLocation();
  return <output aria-label="ubicación">{pathname + search}</output>;
}

const montar = () =>
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
      <Ubicacion />
    </MemoryRouter>,
  );

const guardado = () => JSON.parse(localStorage.getItem("sesion") ?? "{}").state;

test("al cargar, los permisos de /auth/me mandan sobre los guardados", async () => {
  respuestaMe = () => responder("/auth/me", "get", 200, asistente);
  montar();
  // Mientras llega la respuesta se pinta con lo guardado.
  expect(screen.getByRole("link", { name: "Crear evento" })).toBeInTheDocument();

  await waitFor(() =>
    expect(screen.queryByRole("link", { name: "Crear evento" })).not.toBeInTheDocument(),
  );
  expect(useSession.getState().user?.permisos).toEqual([]);
  expect(useSession.getState().user?.role).toBe("ATTENDEE");
  expect(guardado().user.permisos).toEqual([]);
  expect(guardado().accessToken).toBe("token-abc");
});

test("pide /auth/me una sola vez por carga", async () => {
  respuestaMe = () => responder("/auth/me", "get", 200, asistente);
  montar();
  await waitFor(() => expect(useSession.getState().user?.role).toBe("ATTENDEE"));
  expect(llamadasMe).toBe(1);
});

test("si /auth/me responde 401 se cierra la sesión y lleva a /login?next=", async () => {
  respuestaMe = () =>
    responder("/auth/me", "get", 401, {
      type: "unauthorized",
      title: "Sesión inválida",
      status: 401,
      trace_id: "t-1",
    });
  montar();

  await waitFor(() => expect(screen.getByLabelText("ubicación")).toHaveTextContent("/login?next="));
  expect(useSession.getState().accessToken).toBeNull();
});

test("ante un error de red se queda con lo guardado", async () => {
  respuestaMe = () => HttpResponse.error();
  montar();

  await waitFor(() => expect(llamadasMe).toBe(1));
  expect(screen.getByRole("link", { name: "Crear evento" })).toBeInTheDocument();
  expect(useSession.getState().user?.permisos).toEqual(["evento:crear"]);
  expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/$/);
});

test("la respuesta de /auth/me del token A no pisa al usuario de la sesión B", async () => {
  let soltar!: () => void;
  const espera = new Promise<void>((resolver) => (soltar = resolver));
  respuestaMe = async () => {
    await espera;
    return responder("/auth/me", "get", 200, asistente);
  };
  montar();
  await waitFor(() => expect(llamadasMe).toBe(1));

  const otra: Perfil = { ...organizador, id: "otro-id", full_name: "Otra persona" };
  act(() => useSession.getState().iniciarSesion(otra, "token-b", 3600));
  soltar();
  await act(() => new Promise((r) => setTimeout(r, 50)));

  expect(useSession.getState().accessToken).toBe("token-b");
  expect(useSession.getState().user).toEqual(otra);
});

test("sin sesión guardada no pide /auth/me", async () => {
  useSession.getState().cerrarSesion();
  montar();
  await screen.findByRole("heading", { name: "Próximos eventos" });
  expect(llamadasMe).toBe(0);
});
