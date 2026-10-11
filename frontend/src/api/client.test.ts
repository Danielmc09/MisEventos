import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { useSession } from "../stores/session";
import { api } from "./client";
import { ApiError } from "./errors";

const API = "http://localhost:8000";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useSession.getState().clear();
});
afterAll(() => server.close());

const problem = (status: number, body: Record<string, unknown>) =>
  HttpResponse.json(body, { status, headers: { "Content-Type": "application/problem+json" } });

test("convierte un 409 problem+json en un ApiError con su title y su traceId", async () => {
  server.use(
    http.post(`${API}/events/1/registrations`, () =>
      problem(409, {
        type: "capacity-full",
        title: "El evento no tiene cupos",
        status: 409,
        detail: "El evento alcanzó su capacidad de 50 personas.",
        trace_id: "8f2c-trace",
      }),
    ),
  );

  const error = await api("/events/1/registrations", { method: "POST" }).catch((e) => e);

  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({
    status: 409,
    type: "capacity-full",
    title: "El evento no tiene cupos",
    detail: "El evento alcanzó su capacidad de 50 personas.",
    traceId: "8f2c-trace",
  });
});

test("ante un 401 vacía la sesión", async () => {
  useSession.getState().setToken("token-vencido");
  server.use(
    http.get(`${API}/auth/me`, () =>
      problem(401, { type: "unauthorized", title: "Sesión inválida", status: 401 }),
    ),
  );

  const error = await api("/auth/me").catch((e) => e);

  expect(error).toBeInstanceOf(ApiError);
  expect(error.status).toBe(401);
  expect(useSession.getState().accessToken).toBeNull();
});

test("ante un error de red devuelve el título «No se pudo conectar con el servidor»", async () => {
  server.use(http.get(`${API}/events`, () => HttpResponse.error()));

  const error = await api("/events").catch((e) => e);

  expect(error).toBeInstanceOf(ApiError);
  expect(error.title).toBe("No se pudo conectar con el servidor");
});

test("agrega el token de la sesión en el header Authorization", async () => {
  useSession.getState().setToken("abc123");
  let authorization: string | null = null;
  server.use(
    http.get(`${API}/auth/me`, ({ request }) => {
      authorization = request.headers.get("Authorization");
      return HttpResponse.json({ ok: true });
    }),
  );

  await api("/auth/me");

  expect(authorization).toBe("Bearer abc123");
});

test("devuelve el cuerpo JSON de una respuesta exitosa", async () => {
  server.use(http.get(`${API}/events`, () => HttpResponse.json({ items: [], total: 0 })));

  expect(await api("/events")).toEqual({ items: [], total: 0 });
});
