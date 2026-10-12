import { render, screen } from "@testing-library/react";
import { FranjaFecha } from "./FranjaFecha";

const GRADIENTE = "bg-linear-to-br from-primario to-tinta";

test("muestra el día y el mes en un bloque", () => {
  render(<FranjaFecha dia="10" mes="Oct" gradiente={GRADIENTE} />);

  expect(screen.getByText("10")).toBeInTheDocument();
  expect(screen.getByText("Oct")).toBeInTheDocument();
});

test("la franja lleva el gradiente que recibe", () => {
  const { container } = render(<FranjaFecha dia="10" mes="Oct" gradiente={GRADIENTE} />);

  expect(container.firstElementChild).toHaveClass("from-primario", "to-tinta");
});

test("lo que recibe como hijo queda dentro de la franja", () => {
  const { container } = render(
    <FranjaFecha dia="10" mes="Oct" gradiente={GRADIENTE}>
      <span>Publicado</span>
    </FranjaFecha>,
  );

  expect(container.firstElementChild).toContainElement(screen.getByText("Publicado"));
});
