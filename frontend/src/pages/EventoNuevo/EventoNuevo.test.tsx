import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { setupServer } from "msw/node";
import { useEventos } from "../../stores/eventos";
import { API, evento, montar } from "../../test/helpers";
import { responder } from "../../test/msw";
import EventoNuevo from "./EventoNuevo";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useEventos.getState().invalidar();
});
afterAll(() => server.close());

const abrir = () =>
  montar("/eventos/nuevo", [
    ["/eventos/nuevo", <EventoNuevo />],
    ["/eventos/:id", <p>Detalle del evento</p>],
  ]);

type Usuario = ReturnType<typeof userEvent.setup>;

async function completar(
  user: Usuario,
  { nombre = "PyCon Bogotá", inicio = "2026-12-20T19:00", fin = "2026-12-20T23:00" } = {},
) {
  await user.type(screen.getByLabelText("Nombre"), nombre);
  await user.type(screen.getByLabelText("Lugar"), "Ágora Bogotá");
  await user.type(screen.getByLabelText("Inicio"), inicio);
  await user.type(screen.getByLabelText("Fin"), fin);
  await user.type(screen.getByLabelText("Capacidad"), "100");
}

const crear = (user: Usuario) => user.click(screen.getByRole("button", { name: "Crear evento" }));

describe("validación en el cliente", () => {
  test("no se envía con fin igual o anterior al inicio y marca el campo", async () => {
    let llamadas = 0;
    server.use(
      http.post(`${API}/events`, () => {
        llamadas++;
        return responder("/events", "post", 201, evento);
      }),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user, { fin: "2026-12-20T19:00" });
    await crear(user);

    expect(screen.getByLabelText("Fin")).toHaveAccessibleDescription(
      "La fecha de fin tiene que ser posterior al inicio",
    );
    expect(llamadas).toBe(0);
  });

  test("un nombre de 2 caracteres no se envía y marca el campo", async () => {
    const user = userEvent.setup();
    abrir();

    await completar(user, { nombre: "Py" });
    await crear(user);

    expect(screen.getByLabelText("Nombre")).toHaveAccessibleDescription(
      "El nombre debe tener entre 3 y 150 caracteres",
    );
  });
});

describe("crear", () => {
  test("envía las fechas como ISO con -05:00, lleva al detalle e invalida el listado", async () => {
    let cuerpo: unknown;
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
      http.post(`${API}/events`, async ({ request }) => {
        cuerpo = await request.json();
        return responder("/events", "post", 201, evento);
      }),
    );
    await useEventos.getState().listar("");
    await useEventos.getState().listar("");
    expect(listados).toBe(1);
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await crear(user);

    expect(await screen.findByText("Detalle del evento")).toBeInTheDocument();
    expect(cuerpo).toMatchObject({
      name: "PyCon Bogotá",
      start_at: "2026-12-20T19:00:00-05:00",
      end_at: "2026-12-20T23:00:00-05:00",
      capacity: 100,
    });
    await useEventos.getState().listar("");
    expect(listados).toBe(2);
    expect(screen.getByLabelText("ubicación")).toHaveTextContent(`/eventos/${evento.id}`);
  });
});

describe("errores del backend", () => {
  test("un 422 muestra cada mensaje en su campo", async () => {
    server.use(
      http.post(`${API}/events`, () =>
        responder("/events", "post", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-1",
          errors: [
            { field: "start_at", message: "La fecha de inicio tiene que estar en el futuro" },
            { field: "capacity", message: "La capacidad es demasiado grande" },
          ],
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await crear(user);

    await screen.findByText("La capacidad es demasiado grande");
    expect(screen.getByLabelText("Inicio")).toHaveAccessibleDescription(
      "La fecha de inicio tiene que estar en el futuro",
    );
    expect(screen.getByLabelText("Capacidad")).toHaveAccessibleDescription(
      "La capacidad es demasiado grande",
    );
    expect(screen.queryByText("Detalle del evento")).not.toBeInTheDocument();
  });

  test("un 422 en la descripción se ve asociado a su campo", async () => {
    server.use(
      http.post(`${API}/events`, () =>
        responder("/events", "post", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-3",
          errors: [{ field: "description", message: "La descripción es demasiado larga" }],
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await crear(user);

    await vi.waitFor(() =>
      expect(screen.getByLabelText("Descripción")).toHaveAccessibleDescription(
        "La descripción es demasiado larga",
      ),
    );
  });

  test("un 422 en un campo sin input aparece como mensaje general con su message", async () => {
    server.use(
      http.post(`${API}/events`, () =>
        responder("/events", "post", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-4",
          errors: [{ field: "organizer_id", message: "El organizador no es válido" }],
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await crear(user);

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("Los datos enviados no son válidos");
    expect(alerta).toHaveTextContent("El organizador no es válido");
  });

  test("otro error muestra su title", async () => {
    server.use(
      http.post(`${API}/events`, () =>
        responder("/events", "post", 403, {
          type: "forbidden",
          title: "No tenés permiso para hacer esto",
          status: 403,
          trace_id: "t-2",
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await crear(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("No tenés permiso para hacer esto");
  });
});
