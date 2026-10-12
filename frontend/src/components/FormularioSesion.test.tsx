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
});
