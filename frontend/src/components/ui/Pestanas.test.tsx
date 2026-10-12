import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Pestanas } from "./Pestanas";

const PESTANAS = [
  { id: "a", titulo: "Próximos" },
  { id: "b", titulo: "Pasados" },
  { id: "c", titulo: "Cancelados" },
];

function Ejemplo() {
  const [activa, setActiva] = useState("a");
  return (
    <Pestanas
      etiqueta="Mis inscripciones"
      pestanas={PESTANAS}
      activa={activa}
      onCambiar={setActiva}
    >
      <p>Contenido de {activa}</p>
    </Pestanas>
  );
}

test("expone una lista de pestañas con la activa seleccionada y su panel asociado", () => {
  render(<Ejemplo />);

  expect(screen.getByRole("tablist", { name: "Mis inscripciones" })).toBeInTheDocument();
  expect(screen.getAllByRole("tab")).toHaveLength(3);
  const activa = screen.getByRole("tab", { name: "Próximos" });
  expect(activa).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Pasados" })).toHaveAttribute("aria-selected", "false");
  expect(screen.getByRole("tabpanel", { name: "Próximos" })).toHaveTextContent("Contenido de a");
});

test("al hacer click en otra pestaña cambia la activa y el panel", async () => {
  render(<Ejemplo />);

  await userEvent.click(screen.getByRole("tab", { name: "Cancelados" }));

  expect(screen.getByRole("tab", { name: "Cancelados" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tabpanel", { name: "Cancelados" })).toHaveTextContent("Contenido de c");
});

test("las flechas mueven la selección entre pestañas", async () => {
  const user = userEvent.setup();
  render(<Ejemplo />);

  screen.getByRole("tab", { name: "Próximos" }).focus();
  await user.keyboard("{ArrowRight}");

  expect(screen.getByRole("tab", { name: "Pasados" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Pasados" })).toHaveFocus();

  await user.keyboard("{ArrowLeft}{ArrowLeft}");
  expect(screen.getByRole("tab", { name: "Cancelados" })).toHaveAttribute("aria-selected", "true");
});
