import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef } from "react";
import { ProveedorAvisos, useAvisos } from "./Avisos";

function Disparadores() {
  const avisar = useAvisos();
  const n = useRef(0);
  return (
    <>
      <button
        type="button"
        onClick={() => avisar({ message: "Reservaste «Testing en Python»", tone: "exito" })}
      >
        Avisar éxito
      </button>
      <button
        type="button"
        onClick={() => avisar({ message: "No se pudo guardar", tone: "error" })}
      >
        Avisar error
      </button>
      <button
        type="button"
        onClick={() => avisar({ message: `Aviso ${++n.current}`, tone: "exito" })}
      >
        Avisar otro
      </button>
    </>
  );
}

const montar = () =>
  render(
    <ProveedorAvisos>
      <Disparadores />
    </ProveedorAvisos>,
  );

afterEach(() => vi.useRealTimers());

describe("aviso de éxito", () => {
  test("se anuncia como status, con su texto y un ícono", async () => {
    const user = userEvent.setup();
    montar();

    await user.click(screen.getByRole("button", { name: "Avisar éxito" }));

    expect(screen.getByRole("status")).toHaveTextContent("Reservaste «Testing en Python»");
    expect(screen.getByRole("img", { name: "Éxito" })).toBeInTheDocument();
  });

  test("se cierra solo a los 4 segundos", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    montar();

    await user.click(screen.getByRole("button", { name: "Avisar éxito" }));
    act(() => vi.advanceTimersByTime(3999));
    expect(screen.getByRole("status")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  test("la X lo cierra antes", async () => {
    const user = userEvent.setup();
    montar();

    await user.click(screen.getByRole("button", { name: "Avisar éxito" }));
    await user.click(screen.getByRole("button", { name: "Cerrar aviso" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("aviso de error", () => {
  test("se anuncia como alert, con su texto y un ícono", async () => {
    const user = userEvent.setup();
    montar();

    await user.click(screen.getByRole("button", { name: "Avisar error" }));

    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo guardar");
    expect(screen.getByRole("img", { name: "Error" })).toBeInTheDocument();
  });
});

test("como mucho hay 3 a la vez, el más nuevo arriba: al llegar el cuarto se va el más viejo", async () => {
  const user = userEvent.setup();
  montar();

  for (let i = 0; i < 4; i++) {
    await user.click(screen.getByRole("button", { name: "Avisar otro" }));
  }

  expect(screen.getAllByRole("status").map((s) => s.textContent)).toEqual([
    expect.stringContaining("Aviso 4"),
    expect.stringContaining("Aviso 3"),
    expect.stringContaining("Aviso 2"),
  ]);
});
