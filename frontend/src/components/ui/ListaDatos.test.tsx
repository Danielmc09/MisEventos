import { render, screen } from "@testing-library/react";
import { ListaDatos } from "./ListaDatos";

test("asocia cada etiqueta con su valor", () => {
  render(
    <ListaDatos
      datos={[
        { etiqueta: "Correo electrónico", valor: "ana@mail.com" },
        { etiqueta: "Rol", valor: "Asistente" },
      ]}
    />,
  );

  expect(screen.getAllByRole("term").map((t) => t.textContent)).toEqual([
    "Correo electrónico",
    "Rol",
  ]);
  expect(screen.getAllByRole("definition").map((d) => d.textContent)).toEqual([
    "ana@mail.com",
    "Asistente",
  ]);
});
