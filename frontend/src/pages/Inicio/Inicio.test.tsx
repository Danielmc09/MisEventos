import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http } from "msw";
import { setupServer } from "msw/node";
import { useEventos } from "../../stores/eventos";
import { useSession } from "../../stores/session";
import { API, evento, montar, usuario } from "../../test/helpers";
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

test("el título es Próximos eventos y la bajada invita a inscribirse", async () => {
  server.use(http.get(`${API}/events`, () => responder("/events", "get", 200, pagina([]))));
  abrir();

  expect(await screen.findByRole("heading", { name: "Próximos eventos" })).toBeInTheDocument();
  expect(screen.getByText("Encontrá un evento e inscribite en un minuto")).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Mis Eventos" })).not.toBeInTheDocument();
});

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

  test("el vacío ofrece Quitar filtros, que limpia la búsqueda y el estado", async () => {
    server.use(
      http.get(`${API}/events`, ({ request }) => {
        const url = new URL(request.url);
        return responder("/events", "get", 200, pagina(url.searchParams.has("q") ? [] : [evento]));
      }),
    );
    const user = userEvent.setup();
    abrir("/?q=zzz&estado=cancelados");
    await screen.findByText("No hay eventos que coincidan");

    await user.click(screen.getByRole("button", { name: "Quitar filtros" }));

    expect(await screen.findByRole("link", { name: "PyCon Bogotá" })).toBeInTheDocument();
    expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/$/);
    expect(screen.getByRole("searchbox", { name: "Buscar eventos" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "Estado" })).toHaveValue("publicados");
  });

  test("el vacío sin filtros solo explica, sin Quitar filtros", async () => {
    server.use(http.get(`${API}/events`, () => responder("/events", "get", 200, pagina([]))));
    abrir();

    await screen.findByText("No hay eventos que coincidan");
    expect(screen.queryByRole("button", { name: "Quitar filtros" })).not.toBeInTheDocument();
  });

  test.each([["/?q=zzz"], ["/?estado=cancelados"]])(
    "el vacío con un solo filtro (%s) ofrece Quitar filtros",
    async (ruta) => {
      server.use(http.get(`${API}/events`, () => responder("/events", "get", 200, pagina([]))));
      abrir(ruta);

      await screen.findByText("No hay eventos que coincidan");
      expect(screen.getByRole("button", { name: "Quitar filtros" })).toBeInTheDocument();
    },
  );

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
  // Testing Library solo avanza los timers falsos si ve un `jest` global.
  beforeEach(() => vi.stubGlobal("jest", { advanceTimersByTime: vi.advanceTimersByTime }));
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

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
    expect(pedidos).toEqual(["?status=PUBLISHED"]);

    act(() => vi.advanceTimersByTime(1));

    expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/\?q=pyth$/);
    vi.useRealTimers();
    await waitFor(() => expect(pedidos).toEqual(["?status=PUBLISHED", "?q=pyth&status=PUBLISHED"]));
  });
});

describe("paginación", () => {
  test("Siguiente cambia page en la URL y pide esa página", async () => {
    const pedidos: string[] = [];
    server.use(
      http.get(`${API}/events`, ({ request }) => {
        const url = new URL(request.url);
        pedidos.push(url.search);
        return responder("/events", "get", 200, {
          ...pagina(),
          total: 30,
          pages: 3,
          page: Number(url.searchParams.get("page") ?? 1),
        });
      }),
    );
    const user = userEvent.setup();
    abrir();
    expect(await screen.findByText("Página 1 de 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    expect(await screen.findByText("Página 2 de 3")).toBeInTheDocument();
    expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/\?page=2$/);
    expect(pedidos).toEqual(["?status=PUBLISHED", "?status=PUBLISHED&page=2"]);

    await user.click(screen.getByRole("button", { name: "Anterior" }));

    expect(await screen.findByText("Página 1 de 3")).toBeInTheDocument();
    expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/$/);
  });

  test("con una sola página no muestra la paginación", async () => {
    server.use(http.get(`${API}/events`, () => responder("/events", "get", 200, pagina())));
    abrir();

    await screen.findByRole("link", { name: "PyCon Bogotá" });
    expect(screen.queryByRole("button", { name: "Siguiente" })).not.toBeInTheDocument();
  });
});

const guardarPedidos = (pedidos: string[]) =>
  server.use(
    http.get(`${API}/events`, ({ request }) => {
      pedidos.push(new URL(request.url).search);
      return responder("/events", "get", 200, pagina());
    }),
  );

describe("filtro de estado", () => {
  test("sin filtro elegido pide solo los publicados y el select muestra Publicados", async () => {
    const pedidos: string[] = [];
    guardarPedidos(pedidos);
    abrir();

    await screen.findByRole("link", { name: "PyCon Bogotá" });
    expect(pedidos).toEqual(["?status=PUBLISHED"]);
    expect(screen.getByRole("combobox", { name: "Estado" })).toHaveValue("publicados");
  });

  test("elegir Cancelados lo pone en la URL, pide status=CANCELLED y vuelve a la página 1", async () => {
    const pedidos: string[] = [];
    guardarPedidos(pedidos);
    const user = userEvent.setup();
    abrir("/?page=2");
    await screen.findByRole("link", { name: "PyCon Bogotá" });

    await user.selectOptions(screen.getByRole("combobox", { name: "Estado" }), "Cancelados");

    await waitFor(() => expect(pedidos).toEqual(["?status=PUBLISHED&page=2", "?status=CANCELLED"]));
    expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/\?estado=cancelados$/);
  });

  test("abrir ?estado=cancelados selecciona Cancelados y pide status=CANCELLED", async () => {
    const pedidos: string[] = [];
    guardarPedidos(pedidos);
    abrir("/?estado=cancelados");

    await screen.findByRole("link", { name: "PyCon Bogotá" });
    expect(pedidos).toEqual(["?status=CANCELLED"]);
    expect(screen.getByRole("combobox", { name: "Estado" })).toHaveValue("cancelados");
  });
});

describe("opciones del filtro de estado", () => {
  afterEach(() => useSession.getState().cerrarSesion());
  const opciones = () => screen.getAllByRole("option").map((o) => o.textContent);
  const organizador = {
    ...usuario,
    role: "ORGANIZER" as const,
    permisos: ["evento:crear" as const],
  };

  test("sin sesión solo ofrece Publicados y Cancelados", async () => {
    guardarPedidos([]);
    abrir();

    await screen.findByRole("link", { name: "PyCon Bogotá" });
    expect(opciones()).toEqual(["Publicados", "Cancelados"]);
  });

  test("quien no crea eventos tampoco ve Borradores ni Todos", async () => {
    useSession.getState().iniciarSesion(usuario, "token", 3600);
    guardarPedidos([]);
    abrir();

    await screen.findByRole("link", { name: "PyCon Bogotá" });
    expect(opciones()).toEqual(["Publicados", "Cancelados"]);
  });

  test("quien no ve borradores y abre ?estado=borradores cae en Publicados", async () => {
    const pedidos: string[] = [];
    guardarPedidos(pedidos);
    abrir("/?estado=borradores");

    await screen.findByRole("link", { name: "PyCon Bogotá" });
    expect(pedidos).toEqual(["?status=PUBLISHED"]);
    expect(screen.getByLabelText("Estado")).toHaveValue("publicados");
  });

  test("un valor desconocido en ?estado= cae en Publicados", async () => {
    guardarPedidos([]);
    abrir("/?estado=otra-cosa");

    await screen.findByRole("link", { name: "PyCon Bogotá" });
    expect(screen.getByLabelText("Estado")).toHaveValue("publicados");
  });

  test("un organizador también ofrece Borradores y Todos", async () => {
    useSession.getState().iniciarSesion(organizador, "token", 3600);
    guardarPedidos([]);
    abrir();

    await screen.findByRole("link", { name: "PyCon Bogotá" });
    expect(opciones()).toEqual(["Publicados", "Cancelados", "Borradores", "Todos"]);
  });

  test("con permiso, Todos no manda status y Borradores manda DRAFT", async () => {
    useSession.getState().iniciarSesion(organizador, "token", 3600);
    const pedidos: string[] = [];
    guardarPedidos(pedidos);
    const user = userEvent.setup();
    abrir();
    await screen.findByRole("link", { name: "PyCon Bogotá" });

    await user.selectOptions(screen.getByRole("combobox", { name: "Estado" }), "Todos");
    await waitFor(() => expect(pedidos).toEqual(["?status=PUBLISHED", ""]));
    expect(screen.getByLabelText("ubicación")).toHaveTextContent(/^\/\?estado=todos$/);

    await user.selectOptions(screen.getByRole("combobox", { name: "Estado" }), "Borradores");
    await waitFor(() => expect(pedidos).toEqual(["?status=PUBLISHED", "", "?status=DRAFT"]));
  });
});
