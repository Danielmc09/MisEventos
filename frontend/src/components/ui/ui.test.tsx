import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";
import { AlertaError } from "./AlertaError";
import { Input } from "./Input";
import { Textarea } from "./Textarea";

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

describe("Textarea", () => {
  test("con error lo muestra asociado al campo con aria-describedby", () => {
    render(<Textarea label="Descripción" error="Demasiado larga" />);

    const campo = screen.getByLabelText("Descripción");

    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo).toHaveAccessibleDescription("Demasiado larga");
  });

  test("sin error no marca el campo como inválido", () => {
    render(<Textarea label="Descripción" />);

    expect(screen.getByLabelText("Descripción")).not.toHaveAttribute("aria-invalid");
  });
});

describe("AlertaError", () => {
  test("muestra el título y el detalle en una alerta", () => {
    render(<AlertaError title="No se pudo guardar" detail="La descripción es demasiado larga" />);

    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo guardar");
    expect(screen.getByRole("alert")).toHaveTextContent("La descripción es demasiado larga");
  });
});
