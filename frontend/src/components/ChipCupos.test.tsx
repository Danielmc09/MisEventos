import { render, screen } from "@testing-library/react";
import { ChipCupos } from "./ChipCupos";

test("con cupos de sobra dice cuántos quedan", () => {
  render(<ChipCupos capacidad={100} libres={40} />);

  expect(screen.getByText("Quedan 40 cupos")).toBeInTheDocument();
});

test("con el 10 % de la capacidad o menos son los últimos lugares", () => {
  render(<ChipCupos capacidad={100} libres={10} />);

  expect(screen.getByText("Últimos lugares · quedan 10")).toBeInTheDocument();
  expect(screen.queryByText(/cupos/)).not.toBeInTheDocument();
});

test("con un solo cupo habla en singular", () => {
  render(<ChipCupos capacidad={100} libres={1} />);

  expect(screen.getByText("Últimos lugares · queda 1")).toBeInTheDocument();
});

test("con el 11 % todavía es el caso normal", () => {
  render(<ChipCupos capacidad={100} libres={11} />);

  expect(screen.getByText("Quedan 11 cupos")).toBeInTheDocument();
});

test("sin cupos dice Sin cupos y nada más", () => {
  render(<ChipCupos capacidad={100} libres={0} />);

  expect(screen.getByText("Sin cupos")).toBeInTheDocument();
  expect(screen.queryByText(/Quedan/)).not.toBeInTheDocument();
});

test("en una sesión habla de lugares", () => {
  render(<ChipCupos capacidad={50} libres={30} unidad="lugar" />);

  expect(screen.getByText("Quedan 30 lugares")).toBeInTheDocument();
});

test("en una sesión con un lugar libre dice queda 1", () => {
  render(<ChipCupos capacidad={3} libres={1} unidad="lugar" />);

  expect(screen.getByText("Últimos lugares · queda 1")).toBeInTheDocument();
});

test("es un solo chip", () => {
  const { container } = render(<ChipCupos capacidad={100} libres={5} />);

  expect(container.children).toHaveLength(1);
});
