import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Select } from "./Select";

test("el campo tiene su label visible y sus opciones", async () => {
  render(
    <Select label="Estado" defaultValue="">
      <option value="">Todos</option>
      <option value="DRAFT">Borrador</option>
    </Select>,
  );

  await userEvent.selectOptions(screen.getByLabelText("Estado"), "Borrador");

  expect(screen.getByRole("combobox", { name: "Estado" })).toHaveValue("DRAFT");
});

test("con error lo marca como inválido y lo asocia al campo", () => {
  render(
    <Select label="Estado" error="Elegí un estado">
      <option value="">Todos</option>
    </Select>,
  );

  const campo = screen.getByLabelText("Estado");

  expect(campo).toHaveAttribute("aria-invalid", "true");
  expect(campo).toHaveAccessibleDescription("Elegí un estado");
});

test("sin label visible se nombra con aria-label", () => {
  render(
    <Select aria-label="Rol de Ana">
      <option value="">Todos</option>
    </Select>,
  );

  expect(screen.getByRole("combobox", { name: "Rol de Ana" })).toBeInTheDocument();
  expect(screen.queryByText("Rol de Ana")).not.toBeInTheDocument();
});
