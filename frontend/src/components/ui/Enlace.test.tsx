import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Enlace } from "./Enlace";

test("Enlace navega a la ruta dada", () => {
  render(
    <MemoryRouter>
      <Enlace to="/perfil">Ver mi perfil</Enlace>
    </MemoryRouter>,
  );

  expect(screen.getByRole("link", { name: "Ver mi perfil" })).toHaveAttribute("href", "/perfil");
});

test("la variante tarjeta extiende su área a toda la tarjeta, sin subrayado", () => {
  render(
    <MemoryRouter>
      <Enlace to="/eventos/1" variante="tarjeta">
        PyCon
      </Enlace>
    </MemoryRouter>,
  );

  const enlace = screen.getByRole("link", { name: "PyCon" });
  expect(enlace).toHaveClass("after:absolute", "after:inset-0");
  expect(enlace).not.toHaveClass("underline");
});

test("el anillo de foco de la tarjeta va hacia adentro: el borde de la tarjeta no lo recorta", () => {
  render(
    <MemoryRouter>
      <Enlace to="/eventos/1" variante="tarjeta">
        PyCon
      </Enlace>
    </MemoryRouter>,
  );

  const enlace = screen.getByRole("link", { name: "PyCon" });
  expect(enlace).toHaveClass(
    "focus-visible:after:outline-3",
    "focus-visible:after:outline-foco",
    "focus-visible:after:-outline-offset-3",
  );
  expect(enlace).not.toHaveClass("focus-visible:after:outline-offset-2");
});
