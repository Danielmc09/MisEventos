import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http } from "msw";
import { setupServer } from "msw/node";
import { useSession } from "../../stores/session";
import { API, montar, usuario } from "../../test/helpers";
import { responder } from "../../test/msw";
import Perfil from "../Perfil/Perfil";
import CambiarContrasena from "./CambiarContrasena";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => useSession.getState().iniciarSesion(usuario, "token-viejo", 3600));
afterEach(() => {
  server.resetHandlers();
  useSession.getState().cerrarSesion();
});
afterAll(() => server.close());

const montarPantalla = () =>
  montar("/cambiar-contrasena", [
    ["/cambiar-contrasena", <CambiarContrasena />],
    ["/perfil", <Perfil />],
  ]);

const claveVieja = crypto.randomUUID();
const claveNueva = crypto.randomUUID();

async function completar(user: ReturnType<typeof userEvent.setup>, confirmacion = claveNueva) {
  await user.type(screen.getByLabelText("Contraseña actual"), claveVieja);
  await user.type(screen.getByLabelText("Contraseña nueva"), claveNueva);
  await user.type(screen.getByLabelText("Confirmá la contraseña nueva"), confirmacion);
  await user.click(screen.getByRole("button", { name: /cambiar contraseña/i }));
}

const tokenNuevo = {
  access_token: "token-nuevo",
  token_type: "bearer",
  expires_in: 3600,
} as const;

test("con éxito guarda el token nuevo, avisa y lleva a /perfil", async () => {
  let cuerpo: unknown;
  server.use(
    http.patch(`${API}/auth/me/password`, async ({ request }) => {
      cuerpo = await request.json();
      return responder("/auth/me/password", "patch", 200, tokenNuevo);
    }),
  );
  const user = userEvent.setup();
  montarPantalla();

  await completar(user);

  expect(await screen.findByRole("heading", { name: "Perfil" })).toBeInTheDocument();
  expect(screen.getByText("Cambiaste tu contraseña")).toBeInTheDocument();
  expect(useSession.getState().accessToken).toBe("token-nuevo");
  expect(useSession.getState().user).toEqual(usuario);
  expect(cuerpo).toEqual({ current_password: claveVieja, new_password: claveNueva });
});

test.each([
  ["current_password", "Contraseña actual", "La contraseña actual no es correcta"],
  ["new_password", "Contraseña nueva", "La contraseña nueva no puede ser igual a la actual"],
])("un 422 en %s se muestra en ese campo", async (campo, label, mensaje) => {
  server.use(
    http.patch(`${API}/auth/me/password`, () =>
      responder("/auth/me/password", "patch", 422, {
        type: "validation-error",
        title: "Los datos enviados no son válidos",
        status: 422,
        trace_id: "t-1",
        errors: [{ field: campo, message: mensaje }],
      }),
    ),
  );
  const user = userEvent.setup();
  montarPantalla();

  await completar(user);

  expect(await screen.findByLabelText(label)).toHaveAccessibleDescription(mensaje);
  expect(useSession.getState().accessToken).toBe("token-viejo");
});

test("con una confirmación distinta no llama a la API y lo marca en el campo", async () => {
  let llamadas = 0;
  server.use(
    http.patch(`${API}/auth/me/password`, () => {
      llamadas++;
      return responder("/auth/me/password", "patch", 200, tokenNuevo);
    }),
  );
  const user = userEvent.setup();
  montarPantalla();

  await completar(user, crypto.randomUUID());

  expect(screen.getByLabelText("Confirmá la contraseña nueva")).toHaveAccessibleDescription(
    "Las contraseñas no coinciden",
  );
  expect(llamadas).toBe(0);
});

test("mientras se envía el botón queda deshabilitado", async () => {
  server.use(
    http.patch(`${API}/auth/me/password`, async () => {
      await delay(100);
      return responder("/auth/me/password", "patch", 200, tokenNuevo);
    }),
  );
  const user = userEvent.setup();
  montarPantalla();

  await completar(user);

  expect(screen.getByRole("button", { name: /cambiar contraseña/i })).toBeDisabled();
  await screen.findByRole("heading", { name: "Perfil" });
});
