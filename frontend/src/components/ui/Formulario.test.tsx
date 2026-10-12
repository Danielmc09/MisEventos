import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FormEvent } from "react";
import { Formulario, GrupoCampos } from "./Formulario";

test("es un formulario que envía y agrupa sus campos", async () => {
  const onSubmit = vi.fn((e: FormEvent) => e.preventDefault());
  render(
    <Formulario aria-label="Datos del evento" onSubmit={onSubmit}>
      <GrupoCampos>
        <input aria-label="Nombre" />
      </GrupoCampos>
      <button type="submit">Crear evento</button>
    </Formulario>,
  );

  await userEvent.click(screen.getByRole("button", { name: "Crear evento" }));

  expect(screen.getByRole("form", { name: "Datos del evento" })).toContainElement(
    screen.getByLabelText("Nombre"),
  );
  expect(onSubmit).toHaveBeenCalledTimes(1);
});
