import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EstadoVacio } from "./EstadoVacio";

test("dice qué falta y ofrece un botón con verbo que dispara la acción", async () => {
  const onAccion = vi.fn();
  render(<EstadoVacio mensaje="No hay nada" accion="Quitar filtros" onAccion={onAccion} />);

  expect(screen.getByText("No hay nada")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Quitar filtros" }));

  expect(onAccion).toHaveBeenCalledTimes(1);
});

test("sin acción solo dice qué falta, sin botón", () => {
  render(<EstadoVacio mensaje="No hay nada" />);

  expect(screen.getByText("No hay nada")).toBeVisible();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
