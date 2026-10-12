import { screen, within } from "@testing-library/react";
import { http } from "msw";
import { setupServer } from "msw/node";
import { useSession } from "../stores/session";
import { API, evento, montar, usuario } from "../test/helpers";
import { responder } from "../test/msw";
import { PanelInscripciones } from "./PanelInscripciones";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => useSession.getState().iniciarSesion(usuario, "token", 3600));
afterEach(() => {
  server.resetHandlers();
  useSession.getState().cerrarSesion();
});
afterAll(() => server.close());

type Estadisticas = Parameters<typeof responder<"/events/{id_evento}/stats", "get", 200>>[3];

function servir(sessions: Estadisticas["sessions"]) {
  server.use(
    http.get(`${API}/events/${evento.id}/stats`, () =>
      responder("/events/{id_evento}/stats", "get", 200, {
        active: 12,
        cancelled: 3,
        capacity: 100,
        available_spots: 88,
        occupancy_pct: 12,
        sessions,
      }),
    ),
    http.get(`${API}/events/${evento.id}/registrations`, () =>
      responder("/events/{id_evento}/registrations", "get", 200, {
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        pages: 1,
      }),
    ),
  );
}

const abrir = () => montar("/", [["/", <PanelInscripciones eventoId={evento.id} version={0} />]]);

describe("ocupación por sesión", () => {
  test("cada sesión muestra su título, reservadas sobre capacidad y una barra accesible", async () => {
    servir([
      { id: "s-1", title: "Testing en Python", reserved: 9, capacity: 10, occupancy_pct: 90 },
      { id: "s-2", title: "Apertura", reserved: 1, capacity: 40, occupancy_pct: 2.5 },
    ]);
    abrir();

    const seccion = await screen.findByRole("group", { name: "Ocupación por sesión" });
    const items = within(seccion).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Testing en Python");
    expect(items[0]).toHaveTextContent("9 / 10");
    expect(
      within(items[0]).getByRole("progressbar", { name: "Ocupación de Testing en Python" }),
    ).toHaveAttribute("aria-valuenow", "90");
    expect(items[1]).toHaveTextContent("Apertura");
    expect(items[1]).toHaveTextContent("1 / 40");
    expect(
      within(items[1]).getByRole("progressbar", { name: "Ocupación de Apertura" }),
    ).toHaveAttribute("aria-valuenow", "2.5");
  });

  test("sin sesiones, esa parte no aparece", async () => {
    servir([]);
    abrir();

    expect(await screen.findByText("Cancelados")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Ocupación por sesión" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("progressbar")).toHaveLength(1);
  });
});
