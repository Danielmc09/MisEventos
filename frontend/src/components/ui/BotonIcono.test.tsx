import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BotonIcono } from "./BotonIcono";
import { IconoLapiz } from "./iconos/IconoLapiz";

const montar = (props = {}) =>
  render(
    <BotonIcono
      etiqueta="Editar la sesión «Apertura»"
      texto="Editar"
      icono={<IconoLapiz />}
      {...props}
    />,
  );

test("tiene el nombre accesible del objeto y avisa el click", async () => {
  const onClick = vi.fn();
  montar({ onClick });

  await userEvent.click(screen.getByRole("button", { name: "Editar la sesión «Apertura»" }));

  expect(onClick).toHaveBeenCalledTimes(1);
});

test("el tooltip aparece con el foco del teclado y se va al salir", async () => {
  const user = userEvent.setup();
  montar();
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

  await user.tab();
  expect(screen.getByRole("tooltip")).toHaveTextContent("Editar");

  await user.tab();
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});

test("el tooltip aparece con el mouse", async () => {
  const user = userEvent.setup();
  montar();

  await user.hover(screen.getByRole("button"));
  expect(screen.getByRole("tooltip")).toHaveTextContent("Editar");

  await user.unhover(screen.getByRole("button"));
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});
