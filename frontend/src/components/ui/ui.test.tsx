import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Button } from "./Button";
import { AlertaError } from "./AlertaError";
import { Input } from "./Input";
import { Textarea } from "./Textarea";
import { Insignia } from "./Insignia";
import { EnlaceBoton } from "./EnlaceBoton";
import { BarraProgreso } from "./BarraProgreso";
import { Tabla } from "./Tabla";
import { Paginacion } from "./Paginacion";
import { TituloSeccion } from "./TituloSeccion";
import { TextoSecundario } from "./TextoSecundario";
import { Cifra } from "./Cifra";

describe("TituloSeccion", () => {
  test("es un encabezado de nivel 2 con el id dado", () => {
    render(<TituloSeccion id="titulo-x">Inscripciones</TituloSeccion>);

    const titulo = screen.getByRole("heading", { level: 2, name: "Inscripciones" });
    expect(titulo).toHaveAttribute("id", "titulo-x");
  });
});

describe("TextoSecundario", () => {
  test("muestra su texto en un párrafo", () => {
    render(<TextoSecundario>Todavía no hay inscritos</TextoSecundario>);

    expect(screen.getByText("Todavía no hay inscritos").tagName).toBe("P");
  });
});

describe("Cifra", () => {
  test("asocia la etiqueta con su valor dentro de una lista de definiciones", () => {
    render(
      <dl>
        <Cifra etiqueta="Inscritos">12</Cifra>
      </dl>,
    );

    expect(screen.getByRole("term")).toHaveTextContent("Inscritos");
    expect(screen.getByRole("definition")).toHaveTextContent("12");
  });
});

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

describe("Button: variantes", () => {
  test.each([
    ["peligro", "bg-red-700"],
    ["secundario", "border-gray-300"],
    ["primario", "bg-indigo-600"],
  ] as const)("la variante %s tiene su estilo", (variante, clase) => {
    render(<Button variante={variante}>Acción</Button>);

    expect(screen.getByRole("button", { name: "Acción" })).toHaveClass(clase);
  });

  test("la variante peligro no conserva el color primario", () => {
    render(<Button variante="peligro">Acción</Button>);

    expect(screen.getByRole("button", { name: "Acción" })).not.toHaveClass("bg-indigo-600");
  });
});

describe("Insignia", () => {
  test("muestra su texto", () => {
    render(<Insignia tono="exito">Estás inscrito</Insignia>);

    expect(screen.getByText("Estás inscrito")).toBeInTheDocument();
  });
});

describe("EnlaceBoton", () => {
  test("es un enlace a la ruta dada", () => {
    render(
      <MemoryRouter>
        <EnlaceBoton to="/login">Iniciá sesión</EnlaceBoton>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Iniciá sesión" })).toHaveAttribute("href", "/login");
  });
});

describe("BarraProgreso", () => {
  test("es una barra de progreso accesible con su valor", () => {
    render(<BarraProgreso etiqueta="Ocupación" valor={42.5} />);

    const barra = screen.getByRole("progressbar", { name: "Ocupación" });
    expect(barra).toHaveAttribute("aria-valuenow", "42.5");
    expect(barra).toHaveAttribute("aria-valuemin", "0");
    expect(barra).toHaveAttribute("aria-valuemax", "100");
  });

  test("acota el valor entre 0 y 100", () => {
    render(<BarraProgreso etiqueta="Ocupación" valor={140} />);

    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });
});

describe("Tabla", () => {
  test("muestra encabezados de columna y una fila por elemento", () => {
    render(
      <Tabla
        descripcion="Inscritos"
        columnas={["Nombre", "Correo"]}
        filas={[
          { id: "1", celdas: ["Ana", "ana@mail.com"] },
          { id: "2", celdas: ["Luis", "luis@mail.com"] },
        ]}
      />,
    );

    expect(screen.getByRole("table", { name: "Inscritos" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Correo" })).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(3);
    expect(screen.getByRole("cell", { name: "luis@mail.com" })).toBeInTheDocument();
  });
});

describe("Paginacion", () => {
  test("con una sola página no se muestra", () => {
    render(<Paginacion pagina={1} paginas={1} onCambiar={() => {}} />);

    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  test("navega a la anterior y a la siguiente, y deshabilita los extremos", async () => {
    const onCambiar = vi.fn();
    render(<Paginacion pagina={1} paginas={3} onCambiar={onCambiar} />);

    expect(screen.getByText("Página 1 de 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));

    expect(onCambiar).toHaveBeenCalledWith(2);
  });
});
