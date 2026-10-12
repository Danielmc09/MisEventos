import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { useSession } from "../stores/session";
import { api } from "./client";
import { responder } from "../test/msw";
import { ApiError } from "./errors";
import type { components } from "./schema";

const API = "http://localhost:8000";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useSession.getState().cerrarSesion();
});
afterAll(() => server.close());

const usuario: components["schemas"]["PerfilConPermisos"] = {
  id: "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  email: "ana@mail.com",
  full_name: "Ana",
  role: "ATTENDEE",
  is_active: true,
  must_change_password: false,
  created_at: "2026-10-11T15:30:00Z",
  permisos: [],
};

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

  const error = await api("/events/1/registrations", { method: "POST" }).catch((e: ApiError) => e);

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
  useSession.getState().iniciarSesion(usuario, "token-vencido", 3600);
  server.use(
    http.get(`${API}/auth/me`, () =>
      responder("/auth/me", "get", 401, {
        type: "unauthorized",
        title: "Sesión inválida",
        status: 401,
        trace_id: "t-1",
      }),
    ),
  );

  const error = await api("/auth/me").catch((e: ApiError) => e);

  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ status: 401 });
  expect(useSession.getState().accessToken).toBeNull();
});

test("ante un error de red devuelve el título «No se pudo conectar con el servidor»", async () => {
  server.use(http.get(`${API}/events`, () => HttpResponse.error()));

  const error = await api("/events").catch((e: ApiError) => e);

  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ title: "No se pudo conectar con el servidor" });
});

test("agrega el token de la sesión en el header Authorization", async () => {
  useSession.getState().iniciarSesion(usuario, "abc123", 3600);
  let authorization: string | null = null;
  server.use(
    http.get(`${API}/auth/me`, ({ request }) => {
      authorization = request.headers.get("Authorization");
      return responder("/auth/me", "get", 200, usuario);
    }),
  );

  await api("/auth/me");

  expect(authorization).toBe("Bearer abc123");
});

test("devuelve el cuerpo JSON de una respuesta exitosa", async () => {
  server.use(http.get(`${API}/events`, () => HttpResponse.json({ items: [], total: 0 })));

  expect(await api("/events")).toEqual({ items: [], total: 0 });
});

test("un error que no es problem+json igual produce un ApiError con título genérico", async () => {
  server.use(http.get(`${API}/events`, () => new HttpResponse("Bad gateway", { status: 502 })));

  const error = await api("/events").catch((e: ApiError) => e);

  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ status: 502, title: "Ocurrió un error inesperado" });
});

test("una respuesta 204 no intenta leer el cuerpo", async () => {
  server.use(http.delete(`${API}/events/1`, () => new HttpResponse(null, { status: 204 })));

  expect(await api("/events/1", { method: "DELETE" })).toBeUndefined();
});

test("envía el cuerpo como JSON", async () => {
  let contentType: string | null = null;
  server.use(
    http.post(`${API}/events`, ({ request }) => {
      contentType = request.headers.get("Content-Type");
      return HttpResponse.json({ id: 1 });
    }),
  );

  await api("/events", { method: "POST", body: JSON.stringify({ title: "Foro" }) });

  expect(contentType).toBe("application/json");
});
