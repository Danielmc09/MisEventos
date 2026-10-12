import { fireEvent, render, screen } from "@testing-library/react";
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

test("Escape quita el tooltip aunque solo haya mouse encima, sin foco", async () => {
  const user = userEvent.setup();
  montar();
  await user.hover(screen.getByRole("button"));
  expect(screen.getByRole("tooltip")).toBeInTheDocument();

  await user.keyboard("{Escape}");

  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});

test("se puede pasar el mouse sobre el tooltip sin que desaparezca", async () => {
  const user = userEvent.setup();
  montar();
  await user.hover(screen.getByRole("button"));

  const tooltip = screen.getByRole("tooltip");
  // El navegador informa a dónde va el puntero (relatedTarget); user-event no lo hace.
  fireEvent.mouseOut(screen.getByRole("button"), { relatedTarget: tooltip });
  fireEvent.mouseOver(tooltip, { relatedTarget: screen.getByRole("button") });

  expect(screen.getByRole("tooltip")).toBeInTheDocument();
  expect(tooltip).not.toHaveClass("pointer-events-none");
});

test("el tooltip se dibuja fuera del contenedor con overflow, para que ninguna tabla lo recorte", async () => {
  const user = userEvent.setup();
  render(
    <div data-testid="tabla" className="overflow-x-auto">
      <BotonIcono etiqueta="Editar a Beto" texto="Editar" icono={<IconoLapiz />} />
    </div>,
  );
  await user.hover(screen.getByRole("button"));

  const tooltip = screen.getByRole("tooltip");
  expect(screen.getByTestId("tabla")).not.toContainElement(tooltip);
  expect(document.body).toContainElement(tooltip);
  expect(tooltip).toHaveClass("fixed");
});

test("soloIcono no muestra el texto junto al ícono en angosto: lo dice solo el tooltip", async () => {
  const user = userEvent.setup();
  montar({ soloIcono: true });

  expect(screen.queryByText("Editar")).not.toBeInTheDocument();
  await user.hover(screen.getByRole("button"));
  expect(screen.getByRole("tooltip")).toHaveTextContent("Editar");
});
