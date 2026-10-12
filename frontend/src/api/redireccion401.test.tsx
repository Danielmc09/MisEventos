import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { http } from "msw";
import { setupServer } from "msw/node";
import { MemoryRouter, useLocation } from "react-router-dom";
import App from "../App";
import { useSession } from "../stores/session";
import { responder } from "../test/msw";
import { api } from "./client";
import type { components } from "./schema";

const API = "http://localhost:8000";
const usuario: components["schemas"]["PerfilConPermisos"] = {
  id: "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  email: "ana@mail.com",
  full_name: "Ana",
  role: "ATTENDEE",
  is_active: true,
  must_change_password: false,
  created_at: "2026-10-11T15:30:00Z",
  permisos: [],
};

const server = setupServer(
  http.get(`${API}/auth/me`, () => responder("/auth/me", "get", 200, usuario)),
  http.get(`${API}/me/registrations`, () =>
    responder("/me/registrations", "get", 401, {
      type: "unauthorized",
      title: "Sesión inválida",
      status: 401,
      trace_id: "t-1",
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
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

test("ante un 401 vacía la sesión y la app termina en /login?next=<ruta donde estaba>", async () => {
  useSession.getState().iniciarSesion(usuario, "token-vencido", 3600);
  montar("/?x=1");
  await screen.findByRole("heading", { name: "Próximos eventos" });

  await act(() => api("/me/registrations").catch(() => undefined));

  await waitFor(() =>
    expect(screen.getByLabelText("ubicación")).toHaveTextContent("/login?next=%2F%3Fx%3D1"),
  );
  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(useSession.getState().accessToken).toBeNull();
});

test("un 401 estando en /login no vuelve a redirigir", async () => {
  montar("/login?next=%2Fperfil");
  await screen.findByRole("heading", { name: "Iniciar sesión" });

  await act(() => api("/me/registrations").catch(() => undefined));

  expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/login\?next=%2Fperfil$/);
});
