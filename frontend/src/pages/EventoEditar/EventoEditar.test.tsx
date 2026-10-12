import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { setupServer } from "msw/node";
import { useEventos } from "../../stores/eventos";
import { useSession } from "../../stores/session";
import { API, evento, montar, usuario } from "../../test/helpers";
import { responder } from "../../test/msw";
import EventoEditar from "./EventoEditar";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useSession.getState().cerrarSesion();
  useEventos.getState().invalidar();
});
afterAll(() => server.close());

const dueno = { ...usuario, id: evento.organizer_id, role: "ORGANIZER" as const };

const abrir = () => {
  server.use(
    http.get(`${API}/events/${evento.id}`, () =>
      responder("/events/{id_evento}", "get", 200, evento),
    ),
  );
  return montar(`/eventos/${evento.id}/editar`, [
    ["/eventos/:id/editar", <EventoEditar />],
    ["/eventos/:id", <p>Detalle del evento</p>],
  ]);
};

describe("edición", () => {
  test("carga los datos, envía solo los campos cambiados y vuelve al detalle", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    let cuerpo: unknown;
    server.use(
      http.patch(`${API}/events/${evento.id}`, async ({ request }) => {
        cuerpo = await request.json();
        return responder("/events/{id_evento}", "patch", 200, { ...evento, capacity: 150 });
      }),
    );
    const user = userEvent.setup();
    abrir();

    expect(await screen.findByLabelText("Nombre")).toHaveValue("PyCon Bogotá");
    expect(screen.getByLabelText("Inicio")).toHaveValue("2026-10-10T20:30");
    expect(screen.getByLabelText("Fin")).toHaveValue("2026-10-11T04:30");
    expect(screen.getByLabelText("Capacidad")).toHaveValue(100);

    await user.clear(screen.getByLabelText("Capacidad"));
    await user.type(screen.getByLabelText("Capacidad"), "150");
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));

    expect(await screen.findByText("Detalle del evento")).toBeInTheDocument();
    expect(cuerpo).toEqual({ capacity: 150 });
  });

  test("si cambia una fecha la envía como ISO con -05:00", async () => {
    useSession.getState().iniciarSesion(dueno, "token", 3600);
    let cuerpo: unknown;
    server.use(
      http.patch(`${API}/events/${evento.id}`, async ({ request }) => {
        cuerpo = await request.json();
        return responder("/events/{id_evento}", "patch", 200, evento);
      }),
    );
    const user = userEvent.setup();
    abrir();

    await user.clear(await screen.findByLabelText("Fin"));
    await user.type(screen.getByLabelText("Fin"), "2026-10-11T05:00");
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await screen.findByText("Detalle del evento");
    expect(cuerpo).toEqual({ end_at: "2026-10-11T05:00:00-05:00" });
  });

  test("quien no es el dueño ni admin no ve el formulario", async () => {
    useSession.getState().iniciarSesion(usuario, "token", 3600);
    abrir();

    expect(await screen.findByText("No tenés permiso para editar este evento")).toBeInTheDocument();
    expect(screen.queryByLabelText("Nombre")).not.toBeInTheDocument();
  });
});
