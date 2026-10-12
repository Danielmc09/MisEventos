import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Chip } from "./Chip";

test.each(["neutro", "exito", "error", "advertencia", "finalizado", "acento"] as const)(
  "el chip de tono %s dice su estado con texto, no solo con color",
  (tono) => {
    render(<Chip tono={tono}>Estado</Chip>);

    expect(screen.getByText("Estado")).toBeVisible();
  },
);

test("sin onQuitar no ofrece ningún botón", () => {
  render(<Chip>Laura Gómez</Chip>);

  expect(screen.getByText("Laura Gómez")).toBeVisible();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

test("con onQuitar ofrece un botón con nombre accesible que lo quita", async () => {
  const onQuitar = vi.fn();
  render(
    <Chip onQuitar={onQuitar} etiquetaQuitar="Quitar a Laura Gómez">
      Laura Gómez
    </Chip>,
  );

  await userEvent.click(screen.getByRole("button", { name: "Quitar a Laura Gómez" }));

  expect(onQuitar).toHaveBeenCalledTimes(1);
});
