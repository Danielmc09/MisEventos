import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { MenuAcciones } from "./MenuAcciones";

function Ruta() {
  return <p data-testid="ruta">{useLocation().pathname}</p>;
}

function montar(onSelect = vi.fn(), ocupado = false) {
  const vista = render(
    <MemoryRouter>
      <Ruta />
      <button type="button">Antes</button>
      <MenuAcciones
        etiqueta="Más acciones"
        ocupado={ocupado}
        items={[
          { texto: "Despublicar", onSelect },
          { texto: "Cancelar evento", onSelect },
          { texto: "Eliminar", onSelect, peligro: true },
          { texto: "Ver perfil", to: "/perfil" },
        ]}
      >
        Más acciones
      </MenuAcciones>
    </MemoryRouter>,
  );
  return { onSelect, user: userEvent.setup(), vista };
}

const disparador = () => screen.getByRole("button", { name: "Más acciones" });

test("cerrado, el botón anuncia un menú colapsado y no muestra opciones", () => {
  montar();

  expect(disparador()).toHaveAttribute("aria-haspopup", "menu");
  expect(disparador()).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
});

test("al abrirlo muestra las opciones y manda el foco a la primera", async () => {
  const { user } = montar();

  await user.click(disparador());

  expect(disparador()).toHaveAttribute("aria-expanded", "true");
  expect(screen.getAllByRole("menuitem").map((i) => i.textContent)).toEqual([
    "Despublicar",
    "Cancelar evento",
    "Eliminar",
    "Ver perfil",
  ]);
  expect(screen.getByRole("menuitem", { name: "Despublicar" })).toHaveFocus();
});

test("con el teclado abre con Flecha abajo y recorre con flechas, Inicio y Fin", async () => {
  const { user } = montar();
  disparador().focus();

  await user.keyboard("{ArrowDown}");
  expect(screen.getByRole("menuitem", { name: "Despublicar" })).toHaveFocus();
  await user.keyboard("{ArrowDown}");
  expect(screen.getByRole("menuitem", { name: "Cancelar evento" })).toHaveFocus();
  await user.keyboard("{ArrowUp}{ArrowUp}");
  expect(screen.getByRole("menuitem", { name: "Ver perfil" })).toHaveFocus();
  await user.keyboard("{Home}");
  expect(screen.getByRole("menuitem", { name: "Despublicar" })).toHaveFocus();
  await user.keyboard("{End}");
  expect(screen.getByRole("menuitem", { name: "Ver perfil" })).toHaveFocus();
});

test("Escape lo cierra y devuelve el foco al botón", async () => {
  const { user } = montar();
  await user.click(disparador());

  await user.keyboard("{Escape}");

  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  expect(disparador()).toHaveFocus();
  expect(disparador()).toHaveAttribute("aria-expanded", "false");
});

test.each(["{Enter}", " "])("%j activa la opción enfocada y cierra el menú", async (tecla) => {
  const { user, onSelect } = montar();
  await user.click(disparador());
  await user.keyboard("{ArrowDown}");

  await user.keyboard(tecla);

  expect(onSelect).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
});

test("una opción con destino es un enlace", async () => {
  const { user } = montar();
  await user.click(disparador());

  expect(screen.getByRole("menuitem", { name: "Ver perfil" })).toHaveAttribute("href", "/perfil");
});

test("un click fuera lo cierra", async () => {
  const { user } = montar();
  await user.click(disparador());

  await user.click(screen.getByRole("button", { name: "Antes" }));

  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
});

test("Tab cierra el menú", async () => {
  const { user } = montar();
  await user.click(disparador());

  await user.keyboard("{Tab}");

  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
});

test("Flecha arriba en el botón abre el menú sobre la última opción", async () => {
  const { user } = montar();
  disparador().focus();

  await user.keyboard("{ArrowUp}");

  expect(screen.getByRole("menuitem", { name: "Ver perfil" })).toHaveFocus();
});

test("Espacio sobre una opción con destino navega", async () => {
  const { user } = montar();
  disparador().focus();
  await user.keyboard("{ArrowUp}");

  await user.keyboard(" ");

  expect(screen.getByTestId("ruta")).toHaveTextContent("/perfil");
});

test("ocupado no abre el menú ni con el mouse ni con el teclado", async () => {
  const { user } = montar(vi.fn(), true);
  disparador().focus();

  await user.click(disparador());
  await user.keyboard("{ArrowDown}");

  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
});

test("mientras trabaja, el foco sigue en el botón, que muestra el spinner y aria-busy", async () => {
  const { user, vista } = montar();
  await user.click(disparador());
  await user.keyboard("{ArrowDown}{Enter}");

  vista.rerender(
    <MemoryRouter>
      <MenuAcciones etiqueta="Más acciones" ocupado items={[{ texto: "Despublicar" }]}>
        Más acciones
      </MenuAcciones>
    </MemoryRouter>,
  );

  expect(disparador()).toHaveFocus();
  expect(disparador()).toHaveAttribute("aria-busy", "true");
  expect(disparador()).toHaveAttribute("aria-disabled", "true");
  expect(disparador()).not.toBeDisabled();
  expect(within(disparador()).getByRole("status")).toBeInTheDocument();
});
