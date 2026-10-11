import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import type { components } from "./api/schema";
import { useSession } from "./stores/session";
import App from "./App";

const usuario: components["schemas"]["UsuarioSalida"] = {
  id: "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  email: "ana@mail.com",
  full_name: "Ana",
  role: "ATTENDEE",
  is_active: true,
  must_change_password: false,
  created_at: "2026-10-11T15:30:00Z",
};

afterEach(() => useSession.getState().cerrarSesion());

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
  expect(await screen.findByRole("heading", { name: "Mis Eventos" })).toBeInTheDocument();
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
  useSession.getState().iniciarSesion(usuario, "token-abc");

  render(
    <MemoryRouter initialEntries={["/perfil"]}>
      <App />
      <Ubicacion />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { name: "Perfil" })).toBeInTheDocument();
  expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/perfil$/);
});
