import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { setupServer } from "msw/node";
import { API, evento, sesion } from "../test/helpers";
import { responder } from "../test/msw";
import { FormularioSesion } from "./FormularioSesion";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// El evento va del 10 de octubre 20:30 al 11 de octubre 04:30, hora de Bogotá.
type Usuario = ReturnType<typeof userEvent.setup>;

function abrir(props: Partial<React.ComponentProps<typeof FormularioSesion>> = {}) {
  const onGuardada = vi.fn();
  const onCancelar = vi.fn();
  render(
    <FormularioSesion evento={evento} onGuardada={onGuardada} onCancelar={onCancelar} {...props} />,
  );
  return { onGuardada, onCancelar };
}

async function completar(
  user: Usuario,
  { titulo = "Testing en Python", inicio = "2026-10-10T21:00", fin = "2026-10-10T22:00" } = {},
) {
  await user.type(screen.getByLabelText("Título"), titulo);
  await user.type(screen.getByLabelText("Inicio"), inicio);
  await user.type(screen.getByLabelText("Fin"), fin);
}

const guardar = (user: Usuario, nombre = "Crear sesión") =>
  user.click(screen.getByRole("button", { name: nombre }));

function espiarPost() {
  const llamadas: unknown[] = [];
  server.use(
    http.post(`${API}/events/${evento.id}/sessions`, async ({ request }) => {
      llamadas.push(await request.json());
      return responder("/events/{id_evento}/sessions", "post", 201, sesion);
    }),
  );
  return llamadas;
}

describe("validación en el cliente", () => {
  test("no se envía con fin igual o anterior al inicio y marca el campo", async () => {
    const llamadas = espiarPost();
    const user = userEvent.setup();
    abrir();

    await completar(user, { fin: "2026-10-10T21:00" });
    await guardar(user);

    expect(screen.getByLabelText("Fin")).toHaveAccessibleDescription(
      "La fecha de fin tiene que ser posterior al inicio",
    );
    expect(llamadas).toHaveLength(0);
  });

  test.each([
    ["empieza antes del evento", { inicio: "2026-10-10T20:00", fin: "2026-10-10T21:00" }, "Inicio"],
    ["termina después del evento", { inicio: "2026-10-11T04:00", fin: "2026-10-11T05:00" }, "Fin"],
  ])("una sesión que %s no se envía y marca el campo", async (_caso, horas, campo) => {
    const llamadas = espiarPost();
    const user = userEvent.setup();
    abrir();

    await completar(user, horas);
    await guardar(user);

    expect(screen.getByLabelText(campo)).toHaveAccessibleDescription(
      "La sesión tiene que caer dentro del horario del evento",
    );
    expect(llamadas).toHaveLength(0);
  });

  test("un título de 2 caracteres y una capacidad mayor a la del evento marcan sus campos", async () => {
    const llamadas = espiarPost();
    const user = userEvent.setup();
    abrir();

    await completar(user, { titulo: "ab" });
    await user.type(screen.getByLabelText("Capacidad"), "101");
    await guardar(user);

    expect(screen.getByLabelText("Título")).toHaveAccessibleDescription(
      "El título debe tener entre 3 y 150 caracteres",
    );
    expect(screen.getByLabelText("Capacidad")).toHaveAccessibleDescription(
      "La capacidad debe ser un número entre 1 y 100",
    );
    expect(llamadas).toHaveLength(0);
  });
});

describe("crear una sesión", () => {
  test("envía los valores con las fechas en hora de Bogotá y avisa con la sesión creada", async () => {
    const llamadas = espiarPost();
    const user = userEvent.setup();
    const { onGuardada } = abrir();

    await completar(user);
    await user.type(screen.getByLabelText("Sala"), "Sala A");
    await user.type(screen.getByLabelText("Capacidad"), "50");
    await guardar(user);

    await vi.waitFor(() => expect(onGuardada).toHaveBeenCalledWith(sesion));
    expect(llamadas).toEqual([
      {
        title: "Testing en Python",
        description: null,
        room: "Sala A",
        start_at: "2026-10-10T21:00:00-05:00",
        end_at: "2026-10-10T22:00:00-05:00",
        capacity: 50,
        speaker_ids: [],
      },
    ]);
  });
});

describe("errores de la API", () => {
  const rutaPost = `${API}/events/${evento.id}/sessions`;

  test("un 409 de cruce muestra su title y su detail", async () => {
    server.use(
      http.post(rutaPost, () =>
        responder("/events/{id_evento}/sessions", "post", 409, {
          type: "speaker-conflict",
          title: "El ponente ya tiene otra sesión en ese horario",
          status: 409,
          detail: "Ana Pérez ya está en «Testing en Python», 10:00 a 11:00",
          trace_id: "t-5",
        }),
      ),
    );
    const user = userEvent.setup();
    const { onGuardada } = abrir();

    await completar(user);
    await guardar(user);

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("El ponente ya tiene otra sesión en ese horario");
    expect(alerta).toHaveTextContent("Ana Pérez ya está en «Testing en Python», 10:00 a 11:00");
    expect(onGuardada).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Crear sesión" })).toBeEnabled();
  });

  test("el errors[] de un 422 aparece en su campo", async () => {
    server.use(
      http.post(rutaPost, () =>
        responder("/events/{id_evento}/sessions", "post", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-6",
          errors: [{ field: "room", message: "La sala es demasiado larga" }],
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await guardar(user);

    await vi.waitFor(() =>
      expect(screen.getByLabelText("Sala")).toHaveAccessibleDescription(
        "La sala es demasiado larga",
      ),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  test("un 422 en speaker_ids se ve asociado al selector de ponentes", async () => {
    server.use(
      http.post(rutaPost, () =>
        responder("/events/{id_evento}/sessions", "post", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-9",
          errors: [{ field: "speaker_ids", message: "Un ponente elegido ya no existe" }],
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await guardar(user);

    await vi.waitFor(() =>
      expect(screen.getByLabelText("Buscar ponente")).toHaveAccessibleDescription(
        "Un ponente elegido ya no existe",
      ),
    );
  });

  test("un 422 en un campo sin input aparece como mensaje general", async () => {
    server.use(
      http.post(rutaPost, () =>
        responder("/events/{id_evento}/sessions", "post", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-10",
          errors: [{ field: "description", message: "La descripción es demasiado larga" }],
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await guardar(user);

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("Los datos enviados no son válidos");
    expect(alerta).toHaveTextContent("La descripción es demasiado larga");
    expect(screen.getByRole("button", { name: "Crear sesión" })).toBeEnabled();
  });

  test("el error del servidor se limpia al editar un campo", async () => {
    server.use(
      http.post(rutaPost, () =>
        responder("/events/{id_evento}/sessions", "post", 409, {
          type: "speaker-conflict",
          title: "El ponente ya tiene otra sesión en ese horario",
          status: 409,
          detail: "Ana Pérez ya está en «Testing en Python», 10:00 a 11:00",
          trace_id: "t-7",
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await guardar(user);
    await screen.findByRole("alert");

    await user.type(screen.getByLabelText("Sala"), "A");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  test("el error de un campo del 422 se limpia al editar ese campo y no los otros", async () => {
    server.use(
      http.post(rutaPost, () =>
        responder("/events/{id_evento}/sessions", "post", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-8",
          errors: [
            { field: "room", message: "La sala es demasiado larga" },
            { field: "capacity", message: "Capacidad inválida" },
          ],
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await guardar(user);
    await vi.waitFor(() =>
      expect(screen.getByLabelText("Sala")).toHaveAccessibleDescription(
        "La sala es demasiado larga",
      ),
    );

    await user.type(screen.getByLabelText("Sala"), "A");

    expect(screen.getByLabelText("Sala")).not.toHaveAccessibleDescription();
    expect(screen.getByLabelText("Capacidad")).toHaveAccessibleDescription("Capacidad inválida");
  });
});

describe("editar una sesión", () => {
  const existente = {
    ...sesion,
    room: "Sala A",
    capacity: 50,
    speakers: [{ id: "p-1", full_name: "Ana Pérez", bio: null }],
  };
  const rutaPatch = `${API}/sessions/${sesion.id}`;

  function espiarPatch() {
    const llamadas: unknown[] = [];
    server.use(
      http.patch(rutaPatch, async ({ request }) => {
        llamadas.push(await request.json());
        return responder("/sessions/{id_sesion}", "patch", 200, existente);
      }),
    );
    return llamadas;
  }

  test("arranca con los valores de la sesión en hora de Bogotá", () => {
    abrir({ sesion: existente });

    expect(screen.getByLabelText("Título")).toHaveValue("Apertura");
    expect(screen.getByLabelText("Sala")).toHaveValue("Sala A");
    expect(screen.getByLabelText("Inicio")).toHaveValue("2026-10-10T20:30");
    expect(screen.getByLabelText("Fin")).toHaveValue("2026-10-10T21:30");
    expect(screen.getByLabelText("Capacidad")).toHaveValue(50);
    expect(screen.getByRole("button", { name: "Guardar cambios" })).toBeInTheDocument();
  });

  test("el PATCH lleva solo lo que cambió", async () => {
    const llamadas = espiarPatch();
    const user = userEvent.setup();
    const { onGuardada } = abrir({ sesion: existente });

    await user.clear(screen.getByLabelText("Fin"));
    await user.type(screen.getByLabelText("Fin"), "2026-10-10T22:00");
    await user.clear(screen.getByLabelText("Sala"));
    await guardar(user, "Guardar cambios");

    await vi.waitFor(() => expect(onGuardada).toHaveBeenCalledWith(existente));
    expect(llamadas).toEqual([{ end_at: "2026-10-10T22:00:00-05:00", room: null }]);
  });

  test("sin cambios no llama a la API", async () => {
    const llamadas = espiarPatch();
    const user = userEvent.setup();
    const { onGuardada } = abrir({ sesion: existente });

    await guardar(user, "Guardar cambios");

    await vi.waitFor(() => expect(onGuardada).toHaveBeenCalledWith(existente));
    expect(llamadas).toHaveLength(0);
  });
});

describe("ponentes de la sesión", () => {
  const ana = {
    id: "b1b1b1b1-0000-4000-8000-000000000001",
    full_name: "Ana Pérez",
    bio: null,
    created_by: evento.organizer_id,
    created_at: "2026-10-01T12:00:00Z",
    updated_at: "2026-10-01T12:00:00Z",
  };

  test("el ponente elegido va en speaker_ids al crear", async () => {
    const llamadas = espiarPost();
    server.use(
      http.get(`${API}/speakers`, () =>
        responder("/speakers", "get", 200, {
          items: [ana],
          total: 1,
          page: 1,
          page_size: 20,
          pages: 1,
        }),
      ),
    );
    const user = userEvent.setup();
    abrir();

    await completar(user);
    await user.type(screen.getByLabelText("Buscar ponente"), "An");
    await user.click(await screen.findByRole("button", { name: "Agregar a Ana Pérez" }));
    await guardar(user);

    await vi.waitFor(() =>
      expect(llamadas).toEqual([expect.objectContaining({ speaker_ids: [ana.id] })]),
    );
  });

  test("quitar un ponente al editar envía la lista nueva completa", async () => {
    const cuerpos: unknown[] = [];
    server.use(
      http.patch(`${API}/sessions/${sesion.id}`, async ({ request }) => {
        cuerpos.push(await request.json());
        return responder("/sessions/{id_sesion}", "patch", 200, sesion);
      }),
    );
    const user = userEvent.setup();
    abrir({ sesion: { ...sesion, speakers: [{ id: ana.id, full_name: "Ana Pérez", bio: null }] } });

    await user.click(screen.getByRole("button", { name: "Quitar a Ana Pérez" }));
    await guardar(user, "Guardar cambios");

    await vi.waitFor(() => expect(cuerpos).toEqual([{ speaker_ids: [] }]));
  });
});
