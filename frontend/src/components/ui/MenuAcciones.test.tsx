import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { MenuAcciones } from "./MenuAcciones";

function montar(onSelect = vi.fn()) {
  render(
    <MemoryRouter>
      <button type="button">Antes</button>
      <MenuAcciones
        etiqueta="Más acciones"
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
  return { onSelect, user: userEvent.setup() };
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
