import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

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
