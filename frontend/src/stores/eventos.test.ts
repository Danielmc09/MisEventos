import { http } from "msw";
import { setupServer } from "msw/node";
import { API, evento } from "../test/helpers";
import { responder } from "../test/msw";
import { useEventos } from "./eventos";
import { useSession } from "./session";
import type { Usuario } from "./session";

const pagina = { items: [evento], total: 1, page: 1, page_size: 12, pages: 1 };
let llamadas: string[] = [];
const server = setupServer(
  http.get(`${API}/events`, ({ request }) => {
    llamadas.push(new URL(request.url).search);
    return responder("/events", "get", 200, pagina);
  }),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
beforeEach(() => {
  llamadas = [];
  vi.useFakeTimers({ toFake: ["Date"] });
  useEventos.getState().invalidar();
});
afterEach(() => {
  vi.useRealTimers();
  useSession.getState().cerrarSesion();
});

const listar = (consulta: string) => useEventos.getState().listar(consulta);

test("una segunda visita con los mismos filtros dentro de 60 s no llama a la API", async () => {
  await listar("q=python");
  vi.advanceTimersByTime(59_000);
  const otra = await listar("q=python");

  expect(llamadas).toEqual(["?q=python"]);
  expect(otra).toEqual(pagina);
});

test("otra combinación de filtros sí llama a la API", async () => {
  await listar("q=python");
  await listar("q=react");

  expect(llamadas).toEqual(["?q=python", "?q=react"]);
});

test("después de invalidar la caché vuelve a llamar a la API", async () => {
  await listar("q=python");
  await listar("q=python");
  expect(llamadas).toHaveLength(1);
  useEventos.getState().invalidar();
  await listar("q=python");

  expect(llamadas).toHaveLength(2);
});

test("pasados 60 s vuelve a llamar a la API", async () => {
  await listar("q=python");
  await listar("q=python");
  expect(llamadas).toHaveLength(1);
  vi.advanceTimersByTime(60_001);
  await listar("q=python");

  expect(llamadas).toHaveLength(2);
});

const usuario = (id: string, role: Usuario["role"]): Usuario => ({
  id,
  email: `${id}@mail.com`,
  full_name: id,
  role,
  is_active: true,
  must_change_password: false,
  created_at: "2026-10-11T15:30:00Z",
  permisos: [],
});

test("al cerrar la sesión el listado se vuelve a pedir", async () => {
  useSession.getState().iniciarSesion(usuario("admin", "ADMIN"), "t", 3600);
  await listar("page=1");
  useSession.getState().salir();
  await listar("page=1");

  expect(llamadas).toHaveLength(2);
});

test("al vencer o rechazarse el token (401) el listado se vuelve a pedir", async () => {
  useSession.getState().iniciarSesion(usuario("admin", "ADMIN"), "t", 3600);
  await listar("page=1");
  useSession.getState().cerrarSesion();
  await listar("page=1");

  expect(llamadas).toHaveLength(2);
});

test("al iniciar sesión el listado visto como anónimo se vuelve a pedir", async () => {
  await listar("page=1");
  useSession.getState().iniciarSesion(usuario("org", "ORGANIZER"), "t", 3600);
  await listar("page=1");

  expect(llamadas).toHaveLength(2);
});

test("renovar el token del mismo usuario no vacía la caché", async () => {
  const ana = usuario("ana", "ATTENDEE");
  useSession.getState().iniciarSesion(ana, "t1", 3600);
  await listar("page=1");
  useSession.getState().iniciarSesion(ana, "t2", 3600);
  await listar("page=1");

  expect(llamadas).toHaveLength(1);
});
