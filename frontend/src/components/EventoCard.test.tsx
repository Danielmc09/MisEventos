import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { components } from "../api/schema";
import { claseGradiente } from "../lib/gradiente";
import { evento } from "../test/helpers";
import { EventoCard } from "./EventoCard";

// El fixture es del 11 de octubre: el estado depende del reloj, así que acá la fecha es relativa a ahora.
const manana = new Date(Date.now() + 24 * 3600_000).toISOString();

const montar = (e = evento) =>
  render(
    <MemoryRouter>
      <EventoCard evento={e} />
    </MemoryRouter>,
  );

test("muestra la fecha en hora de Bogotá, no en UTC", () => {
  montar({ ...evento, start_at: "2026-10-11T01:30:00Z" });

  const fecha = screen.getByText(/10 de oct de 2026/i);
  expect(fecha).toHaveTextContent(/10 de oct de 2026/i);
  expect(fecha).toHaveTextContent(/8:30/);
  expect(fecha).toHaveAttribute("datetime", "2026-10-11T01:30:00Z");
});

test("enlaza el nombre al detalle y muestra el lugar", () => {
  montar();

  expect(screen.getByRole("link", { name: "PyCon Bogotá" })).toHaveAttribute(
    "href",
    `/eventos/${evento.id}`,
  );
  expect(screen.getByText("Ágora Bogotá")).toBeInTheDocument();
});

test("un evento cancelado muestra la insignia Cancelado", () => {
  montar({ ...evento, status: "CANCELLED" });

  expect(screen.getByText("Cancelado")).toBeInTheDocument();
});

test.each([
  ["PUBLISHED", false, "Publicado"],
  ["DRAFT", false, "Borrador"],
  ["PUBLISHED", true, "Finalizado"],
] as const)("estado %s con is_finished=%s muestra %s", (status, is_finished, texto) => {
  montar({ ...evento, status, is_finished, start_at: manana });

  expect(screen.getByText(texto)).toBeInTheDocument();
});

test("un evento publicado que ya empezó muestra En curso", () => {
  montar({ ...evento, start_at: new Date(Date.now() - 2 * 3600_000).toISOString() });

  expect(screen.getByText("En curso")).toBeInTheDocument();
});

test("muestra cuántos cupos quedan", () => {
  montar({ ...evento, available_spots: 7 });

  expect(screen.getByText("Quedan 7 cupos")).toBeInTheDocument();
});

test("con un solo cupo dice que son los últimos lugares", () => {
  montar({ ...evento, available_spots: 1 });

  expect(screen.getByText("Últimos lugares · queda 1")).toBeInTheDocument();
});

test("sin cupos hay un solo chip de cupos: Sin cupos", () => {
  montar({ ...evento, available_spots: 0 });

  expect(screen.getByText("Sin cupos")).toBeInTheDocument();
  expect(screen.queryByText(/Quedan/)).not.toBeInTheDocument();
});

test("con 10 cupos libres de 100 muestra un solo chip: Últimos lugares", () => {
  montar({ ...evento, capacity: 100, available_spots: 10 });

  expect(screen.getByText("Últimos lugares · quedan 10")).toBeInTheDocument();
  expect(screen.queryByText(/cupos/)).not.toBeInTheDocument();
});

test("con 11 cupos libres de 100 es el caso normal", () => {
  montar({ ...evento, capacity: 100, available_spots: 11 });

  expect(screen.getByText("Quedan 11 cupos")).toBeInTheDocument();
  expect(screen.queryByText(/Últimos lugares/)).not.toBeInTheDocument();
});

test.each([
  ["cancelado", { status: "CANCELLED" as const }],
  ["finalizado", { is_finished: true }],
  ["en borrador", { status: "DRAFT" as const }],
])("un evento %s no muestra ningún chip de cupos", (_estado, cambio) => {
  montar({ ...evento, capacity: 100, available_spots: 5, start_at: manana, ...cambio });

  expect(screen.queryByText(/Últimos lugares|cupos/)).not.toBeInTheDocument();
});

test("un evento finalizado sin cupos no muestra el chip Sin cupos", () => {
  montar({ ...evento, available_spots: 0, is_finished: true, start_at: manana });

  expect(screen.queryByText("Sin cupos")).not.toBeInTheDocument();
});

test("la tarjeta tiene un solo enlace, y es el del título", () => {
  montar();

  expect(screen.getAllByRole("link")).toHaveLength(1);
  expect(screen.getByRole("heading", { name: "PyCon Bogotá" })).toContainElement(
    screen.getByRole("link", { name: "PyCon Bogotá" }),
  );
  expect(screen.getByRole("link")).toHaveClass("after:inset-0");
});

test("el bloque de fecha muestra el día y el mes de Bogotá", () => {
  montar({ ...evento, start_at: "2026-10-11T01:30:00Z" });

  expect(screen.getByText("10")).toBeInTheDocument();
  expect(screen.getByText("Oct")).toBeInTheDocument();
});

test("la franja usa el gradiente que corresponde al nombre", () => {
  montar();

  expect(screen.getByRole("article").innerHTML).toContain(claseGradiente("PyCon Bogotá"));
  expect(claseGradiente("PyCon Bogotá")).not.toBe("");
});

test("lo que recibe como hijo queda dentro de la tarjeta", () => {
  render(
    <MemoryRouter>
      <EventoCard evento={evento}>
        <p>Detalle extra</p>
      </EventoCard>
    </MemoryRouter>,
  );

  expect(screen.getByRole("article")).toContainElement(screen.getByText("Detalle extra"));
});

describe("con el resumen del evento (sin cupos)", () => {
  const resumen: components["schemas"]["ResumenEvento"] = {
    id: evento.id,
    name: "PyCon Bogotá",
    start_at: "2026-10-11T01:30:00Z",
    location: "Ágora Bogotá",
    status: "PUBLISHED",
    is_finished: false,
  };

  test("muestra nombre, fecha y lugar pero no los cupos", () => {
    render(
      <MemoryRouter>
        <EventoCard evento={resumen} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "PyCon Bogotá" })).toBeInTheDocument();
    expect(screen.getByText(/10 de oct de 2026/i)).toBeInTheDocument();
    expect(screen.getByText("Ágora Bogotá")).toBeInTheDocument();
    expect(screen.queryByText(/Quedan/)).not.toBeInTheDocument();
  });

  test("un evento cancelado por el organizador muestra la insignia Evento cancelado", () => {
    render(
      <MemoryRouter>
        <EventoCard evento={{ ...resumen, status: "CANCELLED" }} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Evento cancelado")).toBeInTheDocument();
  });
});
