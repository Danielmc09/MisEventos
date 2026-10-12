import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { useSession } from "../../stores/session";
import { API, evento, montar, usuario } from "../../test/helpers";
import { responder } from "../../test/msw";
import Login from "../Login/Login";
import Perfil from "./Perfil";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  useSession.getState().iniciarSesion(usuario, "token-abc", 3600);
  servirInscripciones([]);
});
afterEach(() => {
  server.resetHandlers();
  useSession.getState().cerrarSesion();
});
afterAll(() => server.close());

const montarPerfil = () =>
  montar("/perfil", [
    ["/perfil", <Perfil />],
    ["/login", <Login />],
  ]);

test("muestra el email, el nombre y el rol, y un enlace a cambiar la contraseña", () => {
  montarPerfil();

  expect(screen.getByText("ana@mail.com")).toBeInTheDocument();
  expect(screen.getByText("Ana")).toBeInTheDocument();
  expect(screen.getByText("Asistente")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Cambiar contraseña" })).toHaveAttribute(
    "href",
    "/cambiar-contrasena",
  );
});

test('"Cerrar sesión" llama a logout, vacía la sesión y lleva a /login', async () => {
  let autorizacion: string | null = null;
  server.use(
    http.post(`${API}/auth/logout`, ({ request }) => {
      autorizacion = request.headers.get("Authorization");
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const user = userEvent.setup();
  montarPerfil();

  await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(autorizacion).toBe("Bearer token-abc");
  expect(useSession.getState().accessToken).toBeNull();
  expect(useSession.getState().user).toBeNull();
});

test("si el logout falla por red, igual vacía la sesión", async () => {
  server.use(http.post(`${API}/auth/logout`, () => HttpResponse.error()));
  const user = userEvent.setup();
  montarPerfil();

  await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

  expect(await screen.findByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  expect(useSession.getState().accessToken).toBeNull();
});

type Pagina = Parameters<typeof responder<"/me/registrations", "get", 200>>[3];
type Inscripcion = Pagina["items"][number];

const inscripcion = (nombre: string, extra: Partial<Inscripcion["event"]> = {}): Inscripcion => ({
  id: `ins-${nombre}`,
  event_id: evento.id,
  status: "ACTIVE",
  created_at: "2026-10-01T12:00:00Z",
  cancelled_at: null,
  event: {
    id: evento.id,
    name: nombre,
    start_at: "2026-10-11T01:30:00Z",
    location: "Ágora Bogotá",
    status: "PUBLISHED",
    is_finished: false,
    ...extra,
  },
  reserved_sessions: [],
});

const pagina = (items: Inscripcion[], extra: Partial<Pagina> = {}): Pagina => ({
  items,
  total: items.length,
  page: 1,
  page_size: 20,
  pages: 1,
  ...extra,
});

/** Responde a /me/registrations y anota con qué parámetros lo pidieron. */
function servirInscripciones(items: Inscripcion[], extra: Partial<Pagina> = {}) {
  const pedidos: URLSearchParams[] = [];
  server.use(
    http.get(`${API}/me/registrations`, ({ request }) => {
      pedidos.push(new URL(request.url).searchParams);
      return responder("/me/registrations", "get", 200, pagina(items, extra));
    }),
  );
  return pedidos;
}

describe("Mis inscripciones", () => {
  test("muestra la sección con tres pestañas y los próximos eventos por defecto", async () => {
    const pedidos = servirInscripciones([inscripcion("PyCon Bogotá")]);
    montarPerfil();

    expect(screen.getByRole("heading", { name: "Mis inscripciones" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Próximos",
      "Pasados",
      "Cancelados",
    ]);
    expect(screen.getByRole("tab", { name: "Próximos" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByRole("link", { name: "PyCon Bogotá" })).toBeInTheDocument();
    expect(pedidos[0].get("status")).toBe("ACTIVE");
    expect(pedidos[0].get("when")).toBe("upcoming");
  });

  describe("sesiones reservadas", () => {
    const reservada = (extra: Partial<Inscripcion["reserved_sessions"][number]> = {}) => ({
      id: "s-1",
      title: "Testing en Python",
      start_at: "2026-10-11T15:00:00Z",
      end_at: "2026-10-11T16:00:00Z",
      room: "Sala C",
      ...extra,
    });

    test("lista debajo de la inscripción próxima cada sesión con horario de Bogotá y sala, en el orden recibido", async () => {
      servirInscripciones([
        {
          ...inscripcion("PyCon Bogotá"),
          reserved_sessions: [
            reservada({
              id: "s-2",
              title: "Apertura",
              start_at: "2026-10-11T13:00:00Z",
              end_at: "2026-10-11T14:00:00Z",
              room: "Sala A",
            }),
            reservada(),
            reservada({ id: "s-3", title: "Cierre", room: null }),
          ],
        },
      ]);
      montarPerfil();

      const lista = await screen.findByRole("list", {
        name: "Sesiones reservadas en PyCon Bogotá",
      });
      const items = within(lista).getAllByRole("listitem");
      expect(items).toHaveLength(3);
      expect(items[0]).toHaveTextContent("Apertura");
      expect(items[0]).toHaveTextContent("08:00 a 09:00");
      expect(items[0]).toHaveTextContent("Sala A");
      expect(items[1]).toHaveTextContent("Testing en Python");
      expect(items[1]).toHaveTextContent("10:00 a 11:00");
      expect(items[1]).toHaveTextContent("Sala C");
      expect(items[2]).toHaveTextContent("Cierre");
      expect(items[2]).toHaveTextContent("Sin sala");
    });

    test("sin reservas no muestra la lista", async () => {
      servirInscripciones([inscripcion("PyCon Bogotá")]);
      montarPerfil();

      expect(await screen.findByRole("link", { name: "PyCon Bogotá" })).toBeInTheDocument();
      expect(screen.queryByRole("list")).not.toBeInTheDocument();
    });

    test("las inscripciones pasadas no listan sesiones", async () => {
      servirInscripciones([
        { ...inscripcion("Evento viejo", { is_finished: true }), reserved_sessions: [reservada()] },
      ]);
      const user = userEvent.setup();
      montarPerfil();

      await user.click(screen.getByRole("tab", { name: "Pasados" }));

      expect(await screen.findByRole("link", { name: "Evento viejo" })).toBeInTheDocument();
      expect(screen.queryByRole("list")).not.toBeInTheDocument();
    });
  });

  test("muestra el spinner mientras carga", () => {
    montarPerfil();

    expect(screen.getByRole("status", { name: "Cargando" })).toBeInTheDocument();
  });

  test("Pasados pide los activos pasados", async () => {
    const pedidos = servirInscripciones([inscripcion("Evento viejo", { is_finished: true })]);
    const user = userEvent.setup();
    montarPerfil();

    await user.click(screen.getByRole("tab", { name: "Pasados" }));

    expect(await screen.findByRole("link", { name: "Evento viejo" })).toBeInTheDocument();
    expect(screen.getByText("Finalizado")).toBeInTheDocument();
    const ultimo = pedidos[pedidos.length - 1];
    expect(ultimo.get("status")).toBe("ACTIVE");
    expect(ultimo.get("when")).toBe("past");
  });

  test("Cancelados pide las canceladas con el when por defecto", async () => {
    const pedidos = servirInscripciones([
      { ...inscripcion("Evento que cancelé"), status: "CANCELLED" },
    ]);
    const user = userEvent.setup();
    montarPerfil();

    await user.click(screen.getByRole("tab", { name: "Cancelados" }));

    expect(await screen.findByRole("link", { name: "Evento que cancelé" })).toBeInTheDocument();
    const ultimo = pedidos[pedidos.length - 1];
    expect(ultimo.get("status")).toBe("CANCELLED");
    expect(ultimo.get("when")).toBeNull();
  });

  test.each([
    ["Próximos", "Todavía no tenés inscripciones"],
    ["Pasados", "Todavía no tenés inscripciones pasadas"],
    ["Cancelados", "Todavía no tenés inscripciones canceladas"],
  ])("la pestaña %s vacía explica qué va ahí y ofrece Ver eventos", async (pestana, mensaje) => {
    const user = userEvent.setup();
    montarPerfil();

    await user.click(screen.getByRole("tab", { name: pestana }));

    expect(await screen.findByText(mensaje)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver eventos" })).toHaveAttribute("href", "/");
  });

  test("un evento cancelado por el organizador se ve con la insignia Evento cancelado", async () => {
    servirInscripciones([inscripcion("Evento caído", { status: "CANCELLED" })]);
    montarPerfil();

    expect(await screen.findByText("Evento cancelado")).toBeInTheDocument();
  });

  test("un error de la API muestra su title", async () => {
    server.use(
      http.get(`${API}/me/registrations`, () =>
        responder("/me/registrations", "get", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-1",
        }),
      ),
    );
    montarPerfil();

    expect(await screen.findByRole("alert")).toHaveTextContent("Los datos enviados no son válidos");
  });

  test("pagina: Siguiente pide la página 2 y cambiar de pestaña vuelve a la 1", async () => {
    const pedidos = servirInscripciones([inscripcion("PyCon Bogotá")], { pages: 2 });
    const user = userEvent.setup();
    montarPerfil();

    await user.click(await screen.findByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(pedidos.some((p) => p.get("page") === "2")).toBe(true));

    await user.click(screen.getByRole("tab", { name: "Pasados" }));
    await waitFor(() => {
      const ultimo = pedidos[pedidos.length - 1];
      expect(ultimo.get("when")).toBe("past");
      expect(ultimo.get("page")).not.toBe("2");
    });
  });
});
