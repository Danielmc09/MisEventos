import { render, screen } from "@testing-library/react";
import { DialogoConfirmacion } from "./DialogoConfirmacion";

test("al abrirse, el foco queda en Volver, la opción segura", () => {
  render(
    <DialogoConfirmacion
      titulo="Eliminar la sesión"
      mensaje="No se puede deshacer."
      confirmar="Sí, eliminar la sesión"
      onConfirmar={() => {}}
      onVolver={() => {}}
    />,
  );

  expect(screen.getByRole("button", { name: "Volver" })).toHaveFocus();
});
