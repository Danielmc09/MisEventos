import { render, screen } from "@testing-library/react";
import { Tarjeta } from "./Tarjeta";

test("por defecto es un artículo con su contenido", () => {
  render(<Tarjeta>Contenido</Tarjeta>);

  expect(screen.getByRole("article")).toHaveTextContent("Contenido");
});

test("puede ser un elemento de lista", () => {
  render(
    <ul>
      <Tarjeta as="li">Sesión</Tarjeta>
    </ul>,
  );

  expect(screen.getByRole("listitem")).toHaveTextContent("Sesión");
});

test("la tarjeta no lleva borde: la profundidad es de sombra", () => {
  render(<Tarjeta>Contenido</Tarjeta>);

  expect(screen.getByRole("article")).toHaveTextContent("Contenido");
  expect(screen.getByRole("article").className).not.toMatch(/\bborder/);
  expect(screen.getByRole("article").className).toMatch(/shadow-tarjeta/);
});

test("el índice escalona la entrada dentro de un grupo chico", () => {
  render(<Tarjeta indice={2}>Contenido</Tarjeta>);

  expect(screen.getByRole("article")).toHaveStyle("--i: 2");
});

test("la entrada no se retrasa más de un grupo chico, aunque la lista sea larga", () => {
  render(<Tarjeta indice={40}>Contenido</Tarjeta>);

  expect(screen.getByRole("article")).toHaveStyle("--i: 5");
});

test("la cabecera va arriba, a todo el ancho, antes del contenido", () => {
  render(<Tarjeta cabecera={<p>Franja</p>}>Contenido</Tarjeta>);

  const tarjeta = screen.getByRole("article");
  expect(tarjeta.firstElementChild).toHaveTextContent("Franja");
  expect(tarjeta).toHaveTextContent("Contenido");
  expect(tarjeta).toHaveClass("overflow-hidden");
});
