import { http } from "msw";
import { setupServer } from "msw/node";
import { API, evento } from "../test/helpers";
import { responder } from "../test/msw";
import { useEventos } from "./eventos";

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
afterEach(() => vi.useRealTimers());

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
