import type { components } from "../api/schema";
import { useSession } from "./session";

const usuario: components["schemas"]["UsuarioSalida"] = {
  id: "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  email: "ana@mail.com",
  full_name: "Ana",
  role: "ATTENDEE",
  is_active: true,
  must_change_password: false,
  created_at: "2026-10-11T15:30:00Z",
};

const guardado = () => JSON.parse(localStorage.getItem("sesion") ?? "null")?.state;

afterEach(() => {
  useSession.getState().cerrarSesion();
});

test("iniciar la sesión guarda el usuario y el token en el store y en localStorage", () => {
  useSession.getState().iniciarSesion(usuario, "token-abc");

  expect(useSession.getState()).toMatchObject({ user: usuario, accessToken: "token-abc" });
  expect(guardado()).toEqual({ user: usuario, accessToken: "token-abc" });
});

test("cerrar la sesión vacía el store y localStorage", () => {
  useSession.getState().iniciarSesion(usuario, "token-abc");

  useSession.getState().cerrarSesion();

  expect(useSession.getState()).toMatchObject({ user: null, accessToken: null });
  expect(guardado()).toEqual({ user: null, accessToken: null });
});
