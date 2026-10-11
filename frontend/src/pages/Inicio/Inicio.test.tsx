import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http } from "msw";
import { setupServer } from "msw/node";
import { useEventos } from "../../stores/eventos";
import { API, evento, montar } from "../../test/helpers";
import { responder } from "../../test/msw";
import Inicio from "./Inicio";

const pagina = (items = [evento]) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 12,
  pages: items.length ? 1 : 0,
});

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useEventos.getState().invalidar();
});
afterAll(() => server.close());

const abrir = (ruta = "/") => montar(ruta, [["/", <Inicio />]]);

describe("estados del listado", () => {
  test("muestra el spinner mientras carga y después las tarjetas", async () => {
    server.use(
      http.get(`${API}/events`, async () => {
        await delay(50);
        return responder("/events", "get", 200, pagina());
      }),
    );
    abrir();

    expect(screen.getByRole("status", { name: "Cargando" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "PyCon Bogotá" })).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Cargando" })).not.toBeInTheDocument();
  });

  test("sin resultados muestra el mensaje de vacío", async () => {
    server.use(http.get(`${API}/events`, () => responder("/events", "get", 200, pagina([]))));
    abrir();

    expect(await screen.findByText("No hay eventos que coincidan")).toBeInTheDocument();
  });

  test("si la API falla muestra el title del error", async () => {
    server.use(
      http.get(`${API}/events`, () =>
        responder("/events", "get", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-1",
        }),
      ),
    );
    abrir();

    expect(await screen.findByRole("alert")).toHaveTextContent("Los datos enviados no son válidos");
  });
});

describe("buscador", () => {
  afterEach(() => vi.useRealTimers());

  test("actualiza la URL y pide q a la API recién 300 ms después de la última tecla", async () => {
    const pedidos: string[] = [];
    server.use(
      http.get(`${API}/events`, ({ request }) => {
        pedidos.push(new URL(request.url).search);
        return responder("/events", "get", 200, pagina());
      }),
    );
    abrir();
    await screen.findByRole("link", { name: "PyCon Bogotá" });
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const user = userEvent.setup({ delay: null });

    await user.type(screen.getByRole("searchbox", { name: "Buscar eventos" }), "pyth");
    act(() => vi.advanceTimersByTime(299));

    expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/$/);
    expect(pedidos).toEqual([""]);

    act(() => vi.advanceTimersByTime(1));

    expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/\?q=pyth$/);
    vi.useRealTimers();
    await waitFor(() => expect(pedidos).toEqual(["", "?q=pyth"]));
  });
});
