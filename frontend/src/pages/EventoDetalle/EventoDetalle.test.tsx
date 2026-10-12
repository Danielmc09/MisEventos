import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http } from "msw";
import { setupServer } from "msw/node";
import { useEventos } from "../../stores/eventos";
import { useSession } from "../../stores/session";
import { API, evento, montar, sesion, usuario } from "../../test/helpers";
import { responder } from "../../test/msw";
import EventoDetalle from "./EventoDetalle";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => servirSesiones([]));
afterEach(() => {
  server.resetHandlers();
  useSession.getState().cerrarSesion();
  useEventos.getState().invalidar();
});
afterAll(() => server.close());

const abrir = () =>
  montar(`/eventos/${evento.id}`, [
    ["/eventos/:id", <EventoDetalle />],
    ["/", <p>Página de inicio</p>],
  ]);
const ruta = `${API}/events/${evento.id}`;
const rutaSesiones = `${ruta}/sessions`;

function servirSesiones(sesiones: (typeof sesion)[]) {
  server.use(
    http.get(rutaSesiones, () => responder("/events/{id_evento}/sessions", "get", 200, sesiones)),
  );
}

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
    expect(screen.getByText(/10 de oct.*8:30/)).toBeInTheDocument();
    expect(screen.getByText(/11 de oct.*4:30/)).toBeInTheDocument();
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

const dueno = { ...usuario, id: evento.organizer_id, role: "ORGANIZER" as const };
const admin = { ...usuario, role: "ADMIN" as const };

function servir(e = evento) {
  server.use(http.get(ruta, () => responder("/events/{id_evento}", "get", 200, e)));
}

const problema = (status: 409, title: string) =>
  ({ type: "invalid-transition", title, status, trace_id: "t-9" }) as const;

describe("acciones según quién mira y el estado", () => {
  test("un anónimo y un asistente que no es el dueño no ven acciones", async () => {
    servir();
    const { unmount } = abrir();
    await screen.findByRole("heading", { name: "PyCon Bogotá" });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Editar" })).not.toBeInTheDocument();
    unmount();

    useSession.getState().iniciarSesion(usuario, "token", 3600);
    abrir();
    await screen.findByRole("heading", { name: "PyCon Bogotá" });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  test("el dueño de un evento publicado ve solo las transiciones válidas", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    servir();
    abrir();

    expect(await screen.findByRole("link", { name: "Editar" })).toHaveAttribute(
      "href",
      `/eventos/${evento.id}/editar`,
    );
    expect(screen.getByRole("button", { name: "Despublicar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eliminar" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publicar" })).not.toBeInTheDocument();
  });

  test("el admin ve Publicar en un borrador, y en uno cancelado solo Eliminar", async () => {
    useSession.getState().iniciarSesion(admin, "token", 3600);
    servir({ ...evento, status: "DRAFT" });
    const { unmount } = abrir();
    expect(await screen.findByRole("button", { name: "Publicar" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Despublicar" })).not.toBeInTheDocument();
    unmount();

    servir({ ...evento, status: "CANCELLED" });
    abrir();
    expect(await screen.findByRole("button", { name: "Eliminar" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancelar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Editar" })).not.toBeInTheDocument();
  });
});

describe("ejecutar acciones", () => {
  beforeEach(() => useSession.getState().iniciarSesion(dueno, "token", 3600));

  async function contarListados() {
    let listados = 0;
    server.use(
      http.get(`${API}/events`, () => {
        listados++;
        return responder("/events", "get", 200, {
          items: [],
          total: 0,
          page: 1,
          page_size: 12,
          pages: 0,
        });
      }),
    );
    await useEventos.getState().listar("");
    return () => listados;
  }

  test("publicar avisa, actualiza el estado e invalida el listado", async () => {
    servir({ ...evento, status: "DRAFT" });
    server.use(
      http.post(`${ruta}/publish`, () =>
        responder("/events/{id_evento}/publish", "post", 200, evento),
      ),
    );
    const listados = await contarListados();
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Publicar" }));

    expect(await screen.findByText("Evento publicado")).toBeInTheDocument();
    expect(screen.getByText("Publicado")).toBeInTheDocument();
    await useEventos.getState().listar("");
    expect(listados()).toBe(2);
  });

  test("cancelar pide confirmación y sin confirmar no llama a la API", async () => {
    servir();
    let llamadas = 0;
    server.use(
      http.post(`${ruta}/cancel`, () => {
        llamadas++;
        return responder("/events/{id_evento}/cancel", "post", 200, {
          ...evento,
          status: "CANCELLED",
        });
      }),
    );
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Cancelar" }));
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Volver" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(llamadas).toBe(0);

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    await user.click(screen.getByRole("button", { name: "Sí, cancelar el evento" }));
    expect(await screen.findByText("Evento cancelado")).toBeInTheDocument();
    expect(llamadas).toBe(1);
    expect(screen.getByText("Cancelado")).toBeInTheDocument();
  });

  test("un error de la API se muestra con su title", async () => {
    servir({ ...evento, status: "DRAFT" });
    server.use(
      http.post(`${ruta}/publish`, () =>
        responder(
          "/events/{id_evento}/publish",
          "post",
          409,
          problema(409, "No se puede publicar este evento"),
        ),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Publicar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No se puede publicar este evento");
  });

  test("eliminar pide confirmación, invalida el listado y lleva a /", async () => {
    servir();
    server.use(http.delete(ruta, () => new Response(null, { status: 204 })));
    const listados = await contarListados();
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Eliminar" }));
    await user.click(screen.getByRole("button", { name: "Sí, eliminar el evento" }));

    expect(await screen.findByText("Página de inicio")).toBeInTheDocument();
    await useEventos.getState().listar("");
    expect(listados()).toBe(2);
  });
});

const ana = { id: "p-1", full_name: "Ana Pérez", bio: null };
const luis = { id: "p-2", full_name: "Luis Gómez", bio: null };
const apertura = {
  ...sesion,
  speakers: [ana, luis],
  room: "Sala A",
  capacity: 50,
};
const charla = {
  ...sesion,
  id: "a1b2c3d4-0000-4000-8000-000000000002",
  title: "Charla de pruebas",
  start_at: "2026-10-11T03:00:00Z",
  end_at: "2026-10-11T04:00:00Z",
};
const cierre = {
  ...sesion,
  id: "a1b2c3d4-0000-4000-8000-000000000003",
  title: "Cierre",
  start_at: "2026-10-11T08:00:00Z",
  end_at: "2026-10-11T09:00:00Z",
};

describe("sección de sesiones", () => {
  test("agrupa por día de Bogotá, ordena por hora y muestra horario, sala, capacidad y ponentes", async () => {
    servir();
    servirSesiones([cierre, charla, apertura]);
    abrir();

    const seccion = await screen.findByRole("region", { name: "Sesiones" });
    // 02:00 UTC del 11 ya es el 10 en Bogotá: un agrupado por día UTC los juntaría todos.
    const dias = await within(seccion).findAllByRole("heading", { level: 3 });
    expect(dias).toHaveLength(2);
    expect(dias[0]).toHaveTextContent(/10 de octubre/);
    expect(dias[1]).toHaveTextContent(/11 de octubre/);

    const items = within(seccion).getAllByRole("listitem");
    expect(items.map((i) => within(i).getByRole("heading", { level: 4 }).textContent)).toEqual([
      "Apertura",
      "Charla de pruebas",
      "Cierre",
    ]);
    expect(items[0]).toHaveTextContent("20:30 a 21:30");
    expect(items[1]).toHaveTextContent("22:00 a 23:00");
    expect(items[2]).toHaveTextContent("03:00 a 04:00");
    expect(items[0]).toHaveTextContent("Sala A");
    expect(items[0]).toHaveTextContent("Capacidad: 50");
    expect(items[0]).toHaveTextContent("Ana Pérez, Luis Gómez");
  });

  test("sin sesiones muestra el estado vacío", async () => {
    servir();
    abrir();

    expect(await screen.findByText("Este evento todavía no tiene sesiones")).toBeInTheDocument();
  });

  test("si las sesiones fallan, lo avisa y el evento se sigue viendo", async () => {
    servir();
    server.use(
      http.get(rutaSesiones, () =>
        responder("/events/{id_evento}/sessions", "get", 404, {
          type: "not-found",
          title: "No existe",
          status: 404,
          trace_id: "t-3",
        }),
      ),
    );
    abrir();

    expect(await screen.findByRole("heading", { name: "PyCon Bogotá" })).toBeInTheDocument();
    const seccion = await screen.findByRole("region", { name: "Sesiones" });
    expect(await within(seccion).findByRole("alert")).toHaveTextContent("No existe");
  });

  test("un anónimo y un asistente ajeno no ven los botones de gestión", async () => {
    servir();
    servirSesiones([apertura]);
    const { unmount } = abrir();
    await screen.findByRole("heading", { name: "Apertura" });
    expect(screen.queryByRole("button", { name: /sesión/ })).not.toBeInTheDocument();
    unmount();

    useSession.getState().iniciarSesion(usuario, "token", 3600);
    abrir();
    await screen.findByRole("heading", { name: "Apertura" });
    expect(screen.queryByRole("button", { name: /sesión/ })).not.toBeInTheDocument();
  });

  test.each([
    ["el dueño", dueno],
    ["el admin", admin],
  ])("%s ve Agregar, Editar y Eliminar", async (_quien, quien) => {
    useSession.getState().iniciarSesion(quien, "token", 3600);
    servir();
    servirSesiones([apertura]);
    abrir();

    expect(await screen.findByRole("button", { name: "Agregar sesión" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar sesión Apertura" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eliminar sesión Apertura" })).toBeInTheDocument();
  });

  describe("eliminar una sesión", () => {
    beforeEach(() => useSession.getState().iniciarSesion(dueno, "token", 3600));
    const rutaSesion = `${API}/sessions/${sesion.id}`;

    test("pide confirmación, llama a DELETE, avisa y la saca de la lista", async () => {
      servir();
      servirSesiones([apertura]);
      let llamadas = 0;
      server.use(
        http.delete(rutaSesion, () => {
          llamadas++;
          return new Response(null, { status: 204 });
        }),
      );
      const user = userEvent.setup();
      abrir();

      await user.click(await screen.findByRole("button", { name: "Eliminar sesión Apertura" }));
      expect(screen.getByRole("alertdialog")).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Volver" }));
      expect(llamadas).toBe(0);

      servirSesiones([]);
      await user.click(screen.getByRole("button", { name: "Eliminar sesión Apertura" }));
      await user.click(screen.getByRole("button", { name: "Sí, eliminar la sesión" }));

      expect(await screen.findByText("Sesión eliminada")).toBeInTheDocument();
      expect(llamadas).toBe(1);
      expect(screen.queryByRole("heading", { name: "Apertura" })).not.toBeInTheDocument();
      expect(screen.getByText("Este evento todavía no tiene sesiones")).toBeInTheDocument();
    });

    test("si la API rechaza, el Toast muestra el title del error", async () => {
      servir();
      servirSesiones([apertura]);
      server.use(
        http.delete(rutaSesion, () =>
          responder("/sessions/{id_sesion}", "delete", 409, {
            type: "event-not-editable",
            title: "El evento ya no admite cambios en sus sesiones",
            status: 409,
            trace_id: "t-4",
          }),
        ),
      );
      const user = userEvent.setup();
      abrir();

      await user.click(await screen.findByRole("button", { name: "Eliminar sesión Apertura" }));
      await user.click(screen.getByRole("button", { name: "Sí, eliminar la sesión" }));

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "El evento ya no admite cambios en sus sesiones",
      );
      expect(screen.getByRole("heading", { name: "Apertura" })).toBeInTheDocument();
    });
  });
});
