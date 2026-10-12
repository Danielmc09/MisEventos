import { screen } from "@testing-library/react";
import { delay, http } from "msw";
import { setupServer } from "msw/node";
import { API, evento, montar } from "../../test/helpers";
import { responder } from "../../test/msw";
import EventoDetalle from "./EventoDetalle";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const abrir = () => montar(`/eventos/${evento.id}`, [["/eventos/:id", <EventoDetalle />]]);
const ruta = `${API}/events/${evento.id}`;

describe("estados del detalle", () => {
  test("muestra el spinner mientras carga y después los datos en hora de Bogotá", async () => {
    server.use(
      http.get(ruta, async () => {
        await delay(50);
        return responder("/events/{id_evento}", "get", 200, {
          ...evento,
          description: "Tres días de Python",
        });
      }),
    );
    abrir();

    expect(screen.getByRole("status", { name: "Cargando" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "PyCon Bogotá" })).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Cargando" })).not.toBeInTheDocument();
    expect(screen.getByText(/10 oct.*8:30/)).toBeInTheDocument();
    expect(screen.getByText(/11 oct.*4:30/)).toBeInTheDocument();
    expect(screen.getByText("Ágora Bogotá")).toBeInTheDocument();
    expect(screen.getByText("Tres días de Python")).toBeInTheDocument();
    expect(screen.getByText("Publicado")).toBeInTheDocument();
    expect(screen.getByText("Quedan 100 cupos")).toBeInTheDocument();
  });

  test("un 404 dice que no encontramos el evento", async () => {
    server.use(
      http.get(ruta, () =>
        responder("/events/{id_evento}", "get", 404, {
          type: "not-found",
          title: "No existe",
          status: 404,
          trace_id: "t-1",
        }),
      ),
    );
    abrir();

    expect(await screen.findByText("No encontramos este evento")).toBeInTheDocument();
  });

  test("otro error muestra su title", async () => {
    server.use(
      http.get(ruta, () =>
        responder("/events/{id_evento}", "get", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-2",
        }),
      ),
    );
    abrir();

    expect(await screen.findByRole("alert")).toHaveTextContent("Los datos enviados no son válidos");
  });
});
