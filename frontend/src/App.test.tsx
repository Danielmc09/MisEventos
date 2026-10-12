import { cleanup, render, screen } from "@testing-library/react";
import { http } from "msw";
import { setupServer } from "msw/node";
import { MemoryRouter, useLocation } from "react-router-dom";
import type { components } from "./api/schema";
import { useSession } from "./stores/session";
import { API } from "./test/helpers";
import { responder } from "./test/msw";
import App from "./App";

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

// El perfil pide "Mis inscripciones": sin respuesta simulada, esa petición quedaba colgada y afectaba al test siguiente.
const server = setupServer(
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
afterEach(() => {
  cleanup();
  useSession.getState().cerrarSesion();
});
afterAll(() => server.close());

function Ubicacion() {
  const { pathname, search } = useLocation();
  return <output aria-label="ubicación">{pathname + search}</output>;
}

test("la ruta de inicio carga de forma diferida y muestra el título", async () => {
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );

  expect(screen.getByRole("status", { name: "Cargando" })).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "Próximos eventos" })).toBeInTheDocument();
});

test.each([
  ["/login", "Iniciar sesión"],
  ["/registro", "Crear cuenta"],
])("la ruta %s carga de forma diferida y muestra su título", async (ruta, titulo) => {
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <App />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: titulo })).toBeInTheDocument();
});

test("sin sesión, /perfil lleva a /login?next=%2Fperfil", async () => {
  render(
    <MemoryRouter initialEntries={["/perfil"]}>
      <App />
      <Ubicacion />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent("/login?next=%2Fperfil");
});

test("con sesión, /perfil muestra el perfil", async () => {
  useSession.getState().iniciarSesion(usuario, "token-abc", 3600);

  render(
    <MemoryRouter initialEntries={["/perfil"]}>
      <App />
      <Ubicacion />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "Perfil" })).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/perfil$/);
});

describe("ruta desconocida", () => {
  test.each(["/eventos", "/cualquier-cosa"])(
    "%s muestra la página 404 con un enlace al inicio",
    async (ruta) => {
      render(
        <MemoryRouter initialEntries={[ruta]}>
          <App />
        </MemoryRouter>,
      );

      expect(
        await screen.findByRole("heading", { name: "No encontramos esa página" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Volver al inicio" })).toHaveAttribute("href", "/");
    },
  );

  test("una ruta existente no cae en la 404", async () => {
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "No encontramos esa página" }),
    ).not.toBeInTheDocument();
  });
});
