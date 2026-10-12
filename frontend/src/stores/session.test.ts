import type { components } from "../api/schema";
import { useSession } from "./session";

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

const guardado = () => JSON.parse(localStorage.getItem("sesion") ?? "null")?.state;

afterEach(() => {
  vi.useRealTimers();
  useSession.getState().cerrarSesion();
});

beforeEach(() => vi.useFakeTimers({ toFake: ["Date"] }));

test("iniciar la sesión guarda el usuario y el token en el store y en localStorage", () => {
  vi.setSystemTime(new Date("2026-10-11T12:00:00Z"));
  const vence = Date.now() + 3600 * 1000;

  useSession.getState().iniciarSesion(usuario, "token-abc", 3600);

  expect(useSession.getState()).toMatchObject({
    user: usuario,
    accessToken: "token-abc",
    expiresAt: vence,
  });
  expect(guardado()).toEqual({ user: usuario, accessToken: "token-abc", expiresAt: vence });
});

test("cerrar la sesión vacía el store y localStorage", () => {
  useSession.getState().iniciarSesion(usuario, "token-abc", 3600);

  useSession.getState().cerrarSesion();

  expect(useSession.getState()).toMatchObject({ user: null, accessToken: null, expiresAt: null });
  expect(guardado()).toEqual({ user: null, accessToken: null, expiresAt: null });
});
