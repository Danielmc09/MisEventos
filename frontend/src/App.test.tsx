import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

test("la página inicial muestra el título", () => {
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { name: "Mis Eventos" })).toBeInTheDocument();
});
