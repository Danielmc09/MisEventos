import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";
import { Input } from "./Input";

describe("Button", () => {
  test("en estado de carga queda deshabilitado y muestra el spinner", () => {
    render(<Button loading>Guardar</Button>);

    expect(screen.getByRole("button", { name: /Guardar/ })).toBeDisabled();
    expect(screen.getByRole("status", { name: "Cargando" })).toBeInTheDocument();
  });

  test("sin carga está habilitado, sin spinner, y responde al click", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Guardar</Button>);

    await userEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onClick).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("Input", () => {
  test("con error lo muestra asociado al campo con aria-describedby", () => {
    render(<Input label="Correo" error="El correo no es válido" />);

    const campo = screen.getByLabelText("Correo");

    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo).toHaveAccessibleDescription("El correo no es válido");
    expect(campo.getAttribute("aria-describedby")).toBe(
      screen.getByText("El correo no es válido").id,
    );
  });

  test("sin error no marca el campo como inválido", () => {
    render(<Input label="Correo" />);

    const campo = screen.getByLabelText("Correo");

    expect(campo).not.toHaveAttribute("aria-invalid");
    expect(campo).not.toHaveAttribute("aria-describedby");
  });

  test("conserva el id que le pasan", () => {
    render(<Input label="Correo" id="correo" error="Falta" />);

    expect(screen.getByLabelText("Correo")).toHaveAttribute("id", "correo");
  });
});
