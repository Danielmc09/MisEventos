import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { BotonEnlace, Enlace } from "./Enlace";

test("Enlace navega a la ruta dada", () => {
  render(
    <MemoryRouter>
      <Enlace to="/perfil">Ver mi perfil</Enlace>
    </MemoryRouter>,
  );

  expect(screen.getByRole("link", { name: "Ver mi perfil" })).toHaveAttribute("href", "/perfil");
});

test("BotonEnlace es un botón para una acción, no un enlace", async () => {
  const onClick = vi.fn();
  render(<BotonEnlace onClick={onClick}>Cerrar sesión</BotonEnlace>);

  await userEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));

  expect(onClick).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
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
