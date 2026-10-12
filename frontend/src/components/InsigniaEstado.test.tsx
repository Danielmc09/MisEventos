import { render, screen } from "@testing-library/react";
import { InsigniaEstado } from "./InsigniaEstado";

const HORA = 3600_000;
const en = (horas: number) => new Date(Date.now() + horas * HORA).toISOString();

describe("InsigniaEstado", () => {
  test("un evento publicado que ya empezó y no terminó está En curso", () => {
    render(
      <InsigniaEstado evento={{ status: "PUBLISHED", is_finished: false, start_at: en(-2) }} />,
    );

    expect(screen.getByText("En curso")).toBeInTheDocument();
    expect(screen.queryByText("Publicado")).not.toBeInTheDocument();
  });

  test("un evento publicado que no empezó sigue Publicado", () => {
    render(
      <InsigniaEstado evento={{ status: "PUBLISHED", is_finished: false, start_at: en(24) }} />,
    );

    expect(screen.getByText("Publicado")).toBeInTheDocument();
    expect(screen.queryByText("En curso")).not.toBeInTheDocument();
  });

  test.each([
    ["PUBLISHED", true, "Finalizado"],
    ["DRAFT", false, "Borrador"],
    ["CANCELLED", false, "Cancelado"],
  ] as const)(
    "un evento %s con is_finished=%s ya empezado muestra %s",
    (status, is_finished, texto) => {
      render(<InsigniaEstado evento={{ status, is_finished, start_at: en(-2) }} />);

      expect(screen.getByText(texto)).toBeInTheDocument();
    },
  );
});
