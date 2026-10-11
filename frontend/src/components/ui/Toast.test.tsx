import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toast } from "./Toast";

test("un aviso informativo se anuncia como status", () => {
  render(<Toast message="Guardado" />);

  expect(screen.getByRole("status")).toHaveTextContent("Guardado");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

test("un aviso de error se anuncia como alert y se puede cerrar", async () => {
  const onClose = vi.fn();
  render(<Toast message="No se pudo guardar" tone="error" onClose={onClose} />);

  expect(screen.getByRole("alert")).toHaveTextContent("No se pudo guardar");
  await userEvent.click(screen.getByRole("button", { name: "Cerrar aviso" }));

  expect(onClose).toHaveBeenCalledTimes(1);
});
