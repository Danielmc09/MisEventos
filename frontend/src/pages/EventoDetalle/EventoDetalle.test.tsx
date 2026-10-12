import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http } from "msw";
import { setupServer } from "msw/node";
import type { components } from "../../api/schema";
import { useEventos } from "../../stores/eventos";
import { useSession } from "../../stores/session";
import { API, evento, montar, sesion, usuario } from "../../test/helpers";
import { responder } from "../../test/msw";
import EventoDetalle from "./EventoDetalle";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  servirSesiones([]);
  servirPanel();
});
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

const estadisticas = {
  active: 25,
  cancelled: 3,
  capacity: 100,
  available_spots: 75,
  occupancy_pct: 25,
};
const inscritoFila: components["schemas"]["Inscrito"] = {
  full_name: "Luisa Pérez",
  email: "luisa@mail.com",
  status: "ACTIVE",
  created_at: "2026-10-11T01:30:00Z",
};
const paginaDe = (items: (typeof inscritoFila)[], extra = {}) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 20,
  pages: 1,
  ...extra,
});

/** Responde a las estadísticas y a la lista de inscritos y anota cuántas veces las pidieron. */
function servirPanel(stats: Partial<typeof estadisticas> = {}, items = [inscritoFila], extra = {}) {
  const pedidos = { stats: 0, inscritos: [] as URLSearchParams[] };
  server.use(
    http.get(`${ruta}/stats`, () => {
      pedidos.stats += 1;
      return responder("/events/{id_evento}/stats", "get", 200, { ...estadisticas, ...stats });
    }),
    http.get(`${ruta}/registrations`, ({ request }) => {
      pedidos.inscritos.push(new URL(request.url).searchParams);
      return responder("/events/{id_evento}/registrations", "get", 200, paginaDe(items, extra));
    }),
  );
  return pedidos;
}

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
    expect(screen.getByText("Quedan 100 cupos")).toBeInTheDocument();
  });

  test("un evento publicado que ya empezó se muestra En curso, sin botón de inscripción", async () => {
    useSession.getState().iniciarSesion(usuario, "token", 3600);
    servir(empezado);
    abrir();

    expect(await screen.findByText("En curso")).toBeInTheDocument();
    expect(screen.queryByText("Publicado")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Inscribirme" })).not.toBeInTheDocument();
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

const HORA = 3600_000;
const en = (horas: number) => new Date(Date.now() + horas * HORA).toISOString();
// El fixture es del 11 de octubre: para el comportamiento que depende del reloj, las fechas son relativas a ahora.
const abierto = { ...evento, start_at: en(24), end_at: en(32) };
const empezado = { ...evento, start_at: en(-2), end_at: en(6) };

describe("acciones según quién mira y el estado", () => {
  test("un anónimo y un asistente que no es el dueño no ven acciones", async () => {
    servir(empezado);
    const { unmount } = abrir();
    await screen.findByRole("heading", { name: "PyCon Bogotá" });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Editar" })).not.toBeInTheDocument();
    unmount();

    useSession.getState().iniciarSesion(usuario, "token", 3600);
    servir(empezado);
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
    servir({ ...abierto, status: "DRAFT" });
    server.use(
      http.post(`${ruta}/publish`, () =>
        responder("/events/{id_evento}/publish", "post", 200, abierto),
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

describe("agregar y editar sesiones", () => {
  beforeEach(() => useSession.getState().iniciarSesion(dueno, "token", 3600));

  test("Agregar abre el formulario, crea la sesión, la suma a la lista y avisa", async () => {
    servir();
    servirSesiones([apertura]);
    const cuerpos: unknown[] = [];
    server.use(
      http.post(rutaSesiones, async ({ request }) => {
        cuerpos.push(await request.json());
        return responder("/events/{id_evento}/sessions", "post", 201, charla);
      }),
    );
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Agregar sesión" }));
    const dialogo = screen.getByRole("dialog", { name: "Agregar sesión" });
    await user.type(within(dialogo).getByLabelText("Título"), "Charla de pruebas");
    await user.type(within(dialogo).getByLabelText("Inicio"), "2026-10-10T22:00");
    await user.type(within(dialogo).getByLabelText("Fin"), "2026-10-10T23:00");
    await user.click(within(dialogo).getByRole("button", { name: "Crear sesión" }));

    expect(await screen.findByText("Sesión creada")).toBeInTheDocument();
    expect(cuerpos).toHaveLength(1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Charla de pruebas" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Apertura" })).toBeInTheDocument();
  });

  test("Editar abre el formulario con la sesión, guarda y actualiza la lista", async () => {
    servir();
    servirSesiones([apertura]);
    server.use(
      http.patch(`${API}/sessions/${apertura.id}`, () =>
        responder("/sessions/{id_sesion}", "patch", 200, {
          ...apertura,
          title: "Apertura general",
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Editar sesión Apertura" }));
    const dialogo = screen.getByRole("dialog", { name: "Editar sesión" });
    expect(within(dialogo).getByLabelText("Título")).toHaveValue("Apertura");
    await user.clear(within(dialogo).getByLabelText("Título"));
    await user.type(within(dialogo).getByLabelText("Título"), "Apertura general");
    await user.click(within(dialogo).getByRole("button", { name: "Guardar cambios" }));

    expect(await screen.findByText("Sesión actualizada")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Apertura general" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Apertura" })).not.toBeInTheDocument();
  });

  test("Cancelar o Escape cierran el formulario sin llamar a la API", async () => {
    servir();
    servirSesiones([apertura]);
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Agregar sesión" }));
    const dialogo = screen.getByRole("dialog", { name: "Agregar sesión" });
    await user.click(within(dialogo).getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Agregar sesión" }));
    expect(screen.getByRole("dialog", { name: "Agregar sesión" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test.each([
    ["cancelado", { ...evento, status: "CANCELLED" as const }],
    ["finalizado", { ...evento, is_finished: true }],
  ])("en un evento %s no hay Agregar, Editar ni Eliminar", async (_estado, cerrado) => {
    servir(cerrado);
    servirSesiones([apertura]);
    abrir();

    await screen.findByRole("heading", { name: "Apertura" });
    expect(screen.queryByRole("button", { name: /sesión/ })).not.toBeInTheDocument();
  });
});

const inscrito = { ...abierto, is_registered: true, registered_count: 1, available_spots: 99 };
const lleno = { ...abierto, registered_count: 100, available_spots: 0 };
const rutaInscripcion = `${ruta}/registrations`;
const rutaCancelar = `${ruta}/registrations/me`;

const creada = {
  id: "c1b2c3d4-0000-4000-8000-0000000000aa",
  event_id: evento.id,
  status: "ACTIVE" as const,
  created_at: "2026-10-11T15:30:00Z",
};

const conflicto = (type: string, title: string) => ({
  type,
  title,
  status: 409 as const,
  trace_id: "t-7",
});

const sinBotones = () => {
  for (const nombre of ["Inscribirme", "Sin cupos", "Cancelar inscripción"]) {
    expect(screen.queryByRole("button", { name: nombre })).not.toBeInTheDocument();
  }
  expect(
    screen.queryByRole("link", { name: "Iniciá sesión para inscribirte" }),
  ).not.toBeInTheDocument();
};

describe("botón de inscripción según la situación", () => {
  test("sin sesión invita a iniciar sesión y vuelve al evento", async () => {
    servir(abierto);
    abrir();

    const enlace = await screen.findByRole("link", { name: "Iniciá sesión para inscribirte" });
    expect(enlace).toHaveAttribute(
      "href",
      `/login?next=${encodeURIComponent(`/eventos/${evento.id}`)}`,
    );
    expect(screen.queryByRole("button", { name: "Inscribirme" })).not.toBeInTheDocument();
  });

  test("publicado, con cupo y sin inscripción: Inscribirme", async () => {
    useSession.getState().iniciarSesion(usuario, "token", 3600);
    servir(abierto);
    abrir();

    expect(await screen.findByRole("button", { name: "Inscribirme" })).toBeEnabled();
    expect(screen.queryByText("Estás inscrito")).not.toBeInTheDocument();
  });

  test("inscrito: lo dice y ofrece cancelar", async () => {
    useSession.getState().iniciarSesion(usuario, "token", 3600);
    servir(inscrito);
    abrir();

    expect(await screen.findByText("Estás inscrito")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar inscripción" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Inscribirme" })).not.toBeInTheDocument();
  });

  test("sin cupo: botón deshabilitado Sin cupos", async () => {
    useSession.getState().iniciarSesion(usuario, "token", 3600);
    servir(lleno);
    abrir();

    expect(await screen.findByRole("button", { name: "Sin cupos" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Inscribirme" })).not.toBeInTheDocument();
  });

  test.each([
    ["cancelado", { ...abierto, status: "CANCELLED" as const }],
    ["finalizado", { ...abierto, is_finished: true }],
    ["ya empezado", empezado],
    ["borrador", { ...abierto, status: "DRAFT" as const }],
    ["cancelado con inscripción", { ...inscrito, status: "CANCELLED" as const }],
  ])("un evento %s no tiene botón", async (_estado, e) => {
    useSession.getState().iniciarSesion(usuario, "token", 3600);
    servir(e);
    const { unmount } = abrir();
    await screen.findByRole("heading", { name: "PyCon Bogotá" });
    sinBotones();
    unmount();

    useSession.getState().cerrarSesion();
    abrir();
    await screen.findByRole("heading", { name: "PyCon Bogotá" });
    sinBotones();
  });

  test("el dueño también puede inscribirse a su evento", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    servir(abierto);
    abrir();

    expect(await screen.findByRole("button", { name: "Inscribirme" })).toBeEnabled();
  });
});

describe("inscribirse", () => {
  beforeEach(() => useSession.getState().iniciarSesion(usuario, "token", 3600));

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

  test("avisa, pasa a Estás inscrito, baja los cupos e invalida el listado", async () => {
    servir({ ...abierto, registered_count: 1, available_spots: 100 - 1 });
    let llamadas = 0;
    server.use(
      http.post(rutaInscripcion, () => {
        llamadas++;
        return responder("/events/{id_evento}/registrations", "post", 201, creada);
      }),
    );
    const listados = await contarListados();
    const user = userEvent.setup();
    abrir();

    expect(await screen.findByText("Quedan 99 cupos")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Inscribirme" }));

    expect(await screen.findByText("Te inscribiste al evento")).toBeInTheDocument();
    expect(llamadas).toBe(1);
    expect(screen.getByText("Estás inscrito")).toBeInTheDocument();
    expect(screen.getByText("Quedan 98 cupos")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Inscribirme" })).not.toBeInTheDocument();
    await useEventos.getState().listar("");
    expect(listados()).toBe(2);
  });

  test("capacity-full muestra el title, refresca el evento y deja Sin cupos deshabilitado", async () => {
    let actual = abierto;
    server.use(http.get(ruta, () => responder("/events/{id_evento}", "get", 200, actual)));
    server.use(
      http.post(rutaInscripcion, () => {
        actual = lleno;
        return responder(
          "/events/{id_evento}/registrations",
          "post",
          409,
          conflicto("capacity-full", "El evento no tiene cupos"),
        );
      }),
    );
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Inscribirme" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("El evento no tiene cupos");
    expect(await screen.findByRole("button", { name: "Sin cupos" })).toBeDisabled();
    expect(screen.getByText("Quedan 0 cupos")).toBeInTheDocument();
  });

  test("cualquier 409 refresca el evento", async () => {
    let actual = abierto;
    let lecturas = 0;
    server.use(
      http.get(ruta, () => {
        lecturas++;
        return responder("/events/{id_evento}", "get", 200, actual);
      }),
    );
    server.use(
      http.post(rutaInscripcion, () => {
        actual = inscrito;
        return responder(
          "/events/{id_evento}/registrations",
          "post",
          409,
          conflicto("already-registered", "Ya estás inscrito en este evento"),
        );
      }),
    );
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Inscribirme" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Ya estás inscrito en este evento");
    expect(await screen.findByText("Estás inscrito")).toBeInTheDocument();
    expect(lecturas).toBe(2);
  });
});

describe("cancelar la inscripción", () => {
  beforeEach(() => useSession.getState().iniciarSesion(usuario, "token", 3600));

  test("pide confirmación y sin confirmar no llama a la API", async () => {
    servir(inscrito);
    let llamadas = 0;
    server.use(
      http.delete(rutaCancelar, () => {
        llamadas++;
        return new Response(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Cancelar inscripción" }));
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Volver" }));

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(llamadas).toBe(0);
    expect(screen.getByText("Estás inscrito")).toBeInTheDocument();
  });

  test("confirmado: 204, avisa, vuelve a Inscribirme, sube el cupo e invalida el listado", async () => {
    servir(inscrito);
    server.use(http.delete(rutaCancelar, () => new Response(null, { status: 204 })));
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
    const user = userEvent.setup();
    abrir();

    expect(await screen.findByText("Quedan 99 cupos")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancelar inscripción" }));
    await user.click(screen.getByRole("button", { name: "Sí, cancelar mi inscripción" }));

    expect(await screen.findByText("Cancelaste tu inscripción")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inscribirme" })).toBeInTheDocument();
    expect(screen.queryByText("Estás inscrito")).not.toBeInTheDocument();
    expect(screen.getByText("Quedan 100 cupos")).toBeInTheDocument();
    await useEventos.getState().listar("");
    expect(listados).toBe(2);
  });

  test("un 409 muestra su title y refresca el evento", async () => {
    let actual = inscrito;
    server.use(http.get(ruta, () => responder("/events/{id_evento}", "get", 200, actual)));
    server.use(
      http.delete(rutaCancelar, () => {
        actual = { ...empezado, is_registered: true };
        return responder(
          "/events/{id_evento}/registrations/me",
          "delete",
          409,
          conflicto("event-started", "El evento ya empezó"),
        );
      }),
    );
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Cancelar inscripción" }));
    await user.click(screen.getByRole("button", { name: "Sí, cancelar mi inscripción" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("El evento ya empezó");
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Cancelar inscripción" }),
      ).not.toBeInTheDocument(),
    );
  });
});

describe("panel de inscripciones del dueño", () => {
  const problemaPanel = (title: string) =>
    ({ type: "forbidden", title, status: 403, trace_id: "t-7" }) as const;

  test("el dueño ve las estadísticas con una barra de ocupación accesible", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    servir();
    servirPanel({ active: 12, cancelled: 3, occupancy_pct: 12.5 });
    abrir();

    const panel = await screen.findByRole("region", { name: "Inscripciones" });
    expect(await within(panel).findByText("12")).toBeInTheDocument();
    expect(within(panel).getByText("Inscritos")).toBeInTheDocument();
    expect(within(panel).getByText("Cancelados")).toBeInTheDocument();
    expect(within(panel).getByText("3")).toBeInTheDocument();
    expect(within(panel).getByText(/12,5\s*%/)).toBeInTheDocument();
    expect(within(panel).getByRole("progressbar", { name: "Ocupación" })).toHaveAttribute(
      "aria-valuenow",
      "12.5",
    );
  });

  test("lista los inscritos con nombre, correo, estado y fecha en hora de Bogotá", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    servir();
    servirPanel({}, [
      inscritoFila,
      { ...inscritoFila, full_name: null, email: "sin@nombre.com", status: "CANCELLED" },
    ]);
    abrir();

    const tabla = await screen.findByRole("table", { name: "Lista de inscritos" });
    const filas = within(tabla).getAllByRole("row");
    expect(filas).toHaveLength(3);
    expect(filas[1]).toHaveTextContent("Luisa Pérez");
    expect(filas[1]).toHaveTextContent("luisa@mail.com");
    expect(filas[1]).toHaveTextContent("Activa");
    expect(filas[1]).toHaveTextContent(/10 de oct.*8:30/);
    expect(filas[2]).toHaveTextContent("—");
    expect(filas[2]).toHaveTextContent("Cancelada");
  });

  test("quien se inscribió, canceló y volvió a inscribirse aparece dos veces sin avisos de React", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    servir();
    servirPanel({}, [
      inscritoFila,
      { ...inscritoFila, status: "CANCELLED", created_at: "2026-10-09T15:00:00Z" },
    ]);
    abrir();

    const tabla = await screen.findByRole("table", { name: "Lista de inscritos" });
    expect(within(tabla).getAllByRole("row")).toHaveLength(3);
    expect(within(tabla).getAllByText("luisa@mail.com")).toHaveLength(2);
    expect(error).not.toHaveBeenCalled();
    error.mockRestore();
  });

  test("el admin también ve el panel", async () => {
    useSession.getState().iniciarSesion(admin, "token", 3600);
    servir();
    abrir();

    expect(await screen.findByRole("region", { name: "Inscripciones" })).toBeInTheDocument();
    expect(await screen.findByRole("table", { name: "Lista de inscritos" })).toBeInTheDocument();
  });

  test.each([
    ["un asistente", usuario],
    ["otro organizador", { ...usuario, role: "ORGANIZER" as const }],
  ])("%s no lo ve y no se pide a la API", async (_quien, quien) => {
    useSession.getState().iniciarSesion(quien, "token", 3600);
    servir();
    const pedidos = servirPanel();
    abrir();

    await screen.findByRole("heading", { name: "PyCon Bogotá" });
    expect(screen.queryByRole("region", { name: "Inscripciones" })).not.toBeInTheDocument();
    expect(pedidos.stats).toBe(0);
    expect(pedidos.inscritos).toHaveLength(0);
  });

  test("un anónimo no lo ve y no se pide a la API", async () => {
    servir();
    const pedidos = servirPanel();
    abrir();

    await screen.findByRole("heading", { name: "PyCon Bogotá" });
    expect(screen.queryByRole("region", { name: "Inscripciones" })).not.toBeInTheDocument();
    expect(pedidos.stats).toBe(0);
    expect(pedidos.inscritos).toHaveLength(0);
  });

  test("sin inscritos muestra el estado vacío", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    servir();
    servirPanel({ active: 0, cancelled: 0, occupancy_pct: 0 }, []);
    abrir();

    expect(await screen.findByText("Todavía no hay inscritos")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  test("muestra el spinner mientras cargan las estadísticas y la lista", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    servir();
    server.use(
      http.get(`${ruta}/stats`, async () => {
        await delay(50);
        return responder("/events/{id_evento}/stats", "get", 200, estadisticas);
      }),
      http.get(`${ruta}/registrations`, async () => {
        await delay(50);
        return responder("/events/{id_evento}/registrations", "get", 200, paginaDe([inscritoFila]));
      }),
    );
    abrir();

    const panel = await screen.findByRole("region", { name: "Inscripciones" });
    expect(within(panel).getAllByRole("status", { name: "Cargando" })).toHaveLength(2);
    expect(await within(panel).findByRole("progressbar")).toBeInTheDocument();
    expect(await within(panel).findByRole("table")).toBeInTheDocument();
  });

  test("si fallan las estadísticas muestra su title y la lista sigue visible", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    servir();
    server.use(
      http.get(`${ruta}/stats`, () =>
        responder("/events/{id_evento}/stats", "get", 403, problemaPanel("No tenés permiso")),
      ),
    );
    abrir();

    const panel = await screen.findByRole("region", { name: "Inscripciones" });
    expect(await within(panel).findByRole("alert")).toHaveTextContent("No tenés permiso");
    expect(await within(panel).findByRole("table")).toBeInTheDocument();
    expect(within(panel).queryByRole("progressbar")).not.toBeInTheDocument();
  });

  test("si falla la lista muestra su title y las estadísticas siguen visibles", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    servir();
    server.use(
      http.get(`${ruta}/registrations`, () =>
        responder(
          "/events/{id_evento}/registrations",
          "get",
          403,
          problemaPanel("No podés ver los inscritos"),
        ),
      ),
    );
    abrir();

    const panel = await screen.findByRole("region", { name: "Inscripciones" });
    expect(await within(panel).findByRole("alert")).toHaveTextContent("No podés ver los inscritos");
    expect(await within(panel).findByRole("progressbar")).toBeInTheDocument();
    expect(within(panel).queryByRole("table")).not.toBeInTheDocument();
  });

  test("la lista de inscritos se pagina", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    servir();
    const pedidos = servirPanel({}, [inscritoFila], { pages: 2 });
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: "Siguiente" }));

    await waitFor(() => expect(pedidos.inscritos.some((p) => p.get("page") === "2")).toBe(true));
  });
});
