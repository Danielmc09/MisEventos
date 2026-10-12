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

describe("variante del botón de confirmar", () => {
  const montar = (variante?: "primario" | "peligro") =>
    render(
      <DialogoConfirmacion
        titulo="¿Reactivar a Ana?"
        mensaje="Va a poder volver a entrar."
        confirmar="Reactivar"
        variante={variante}
        onConfirmar={() => {}}
        onVolver={() => {}}
      />,
    );

  test("por defecto es de peligro", () => {
    montar();
    expect(screen.getByRole("button", { name: "Reactivar" })).toHaveClass("bg-error");
  });

  test("con variante primario no es rojo", () => {
    montar("primario");
    const boton = screen.getByRole("button", { name: "Reactivar" });
    expect(boton).toHaveClass("bg-primario");
    expect(boton).not.toHaveClass("bg-error");
  });
});
