import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ControlReserva } from "./ControlReserva";

const manana = new Date(Date.now() + 24 * 3600 * 1000).toISOString();

function dibujar(libres: number) {
  render(
    <ControlReserva
      sesion={{
        start_at: manana,
        is_reserved: false,
        available_spots: libres,
        reserved_count: 3 - libres,
      }}
      inscrito={false}
      eventoPublicado
      onReservar={() => {}}
      onCancelar={() => {}}
    />,
  );
}

// "inscrito" es falso tanto para quien no está inscrito como para un anónimo.
describe("ControlReserva sin inscripción", () => {
  it("avisa que hay que inscribirse y marca los últimos lugares", () => {
    dibujar(1);
    expect(screen.getByText("Inscribite al evento para reservar sesiones")).toBeInTheDocument();
    expect(screen.getByText("Últimos lugares")).toBeInTheDocument();
  });

  it("avisa que hay que inscribirse y marca que no hay cupos", () => {
    dibujar(0);
    expect(screen.getByText("Inscribite al evento para reservar sesiones")).toBeInTheDocument();
    expect(screen.getByText("Sin cupos")).toBeInTheDocument();
  });

  it("no muestra chip si sobran lugares", () => {
    dibujar(3);
    expect(screen.queryByText("Últimos lugares")).not.toBeInTheDocument();
    expect(screen.queryByText("Sin cupos")).not.toBeInTheDocument();
  });
});

describe("ControlReserva con inscripción", () => {
  const dibujarInscrito = (libres: number, reservada = false) =>
    render(
      <ControlReserva
        sesion={{
          start_at: manana,
          is_reserved: reservada,
          available_spots: libres,
          reserved_count: 50 - libres,
        }}
        inscrito
        eventoPublicado
        onReservar={() => {}}
        onCancelar={() => {}}
      />,
    );

  it("con lugares de sobra hay un solo chip, en lugares", () => {
    dibujarInscrito(30);
    expect(screen.getByText("Quedan 30 lugares")).toBeInTheDocument();
  });

  it("con pocos lugares el chip dice cuántos quedan, sin repetirlo aparte", () => {
    dibujarInscrito(4);
    expect(screen.getByText("Últimos lugares · quedan 4")).toBeInTheDocument();
    expect(screen.queryByText("Quedan 4 lugares")).not.toBeInTheDocument();
  });

  it("con la sesión reservada también es un solo chip", () => {
    dibujarInscrito(1, true);
    expect(screen.getByText("Últimos lugares · queda 1")).toBeInTheDocument();
    expect(screen.queryByText("Queda 1 lugar")).not.toBeInTheDocument();
  });
});
