import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { components } from "../api/schema";
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

  const fecha = screen.getByText(/oct/i);
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

test("con un solo cupo habla en singular", () => {
  montar({ ...evento, available_spots: 1 });

  expect(screen.getByText("Queda 1 cupo")).toBeInTheDocument();
});

test("sin cupos lo dice con un chip, además del conteo", () => {
  montar({ ...evento, available_spots: 0 });

  expect(screen.getByText("Sin cupos")).toBeInTheDocument();
  expect(screen.getByText("Quedan 0 cupos")).toBeInTheDocument();
});

test("con cupos no muestra el chip Sin cupos", () => {
  montar({ ...evento, available_spots: 7 });

  expect(screen.queryByText("Sin cupos")).not.toBeInTheDocument();
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
