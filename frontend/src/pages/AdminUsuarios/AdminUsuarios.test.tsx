import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { setupServer } from "msw/node";
import type { components } from "../../api/schema";
import { Encabezado } from "../../components/Encabezado";
import { useSession } from "../../stores/session";
import { API, montar, usuario } from "../../test/helpers";
import { responder } from "../../test/msw";
import Login from "../Login/Login";
import AdminUsuarios from "./AdminUsuarios";

type UsuarioAdmin = components["schemas"]["UsuarioAdmin"];

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useSession.getState().cerrarSesion();
});
afterAll(() => server.close());

const admin = {
  ...usuario,
  id: "a-1",
  email: "admin@mail.com",
  full_name: "Admin",
  role: "ADMIN" as const,
  permisos: ["usuarios:gestionar" as const],
};

const fila = (extra: Partial<UsuarioAdmin>): UsuarioAdmin => ({
  id: "u-1",
  email: "beto@mail.com",
  full_name: "Beto",
  role: "ATTENDEE",
  is_active: true,
  must_change_password: false,
  created_at: "2026-10-01T12:00:00Z",
  updated_at: "2026-10-01T12:00:00Z",
  active_registrations: 2,
  ...extra,
});

const adminFila = fila({
  id: admin.id,
  email: admin.email,
  full_name: "Admin",
  role: "ADMIN",
  active_registrations: 0,
});
const beto = fila({});

function servirUsuarios(items: UsuarioAdmin[] = [adminFila, beto]) {
  const pedidos: URLSearchParams[] = [];
  server.use(
    http.get(`${API}/admin/users`, ({ request }) => {
      pedidos.push(new URL(request.url).searchParams);
      return responder("/admin/users", "get", 200, {
        items,
        total: items.length,
        page: 1,
        page_size: 20,
        pages: 1,
      });
    }),
  );
  return pedidos;
}

function servirPatch(respuesta: "ok" | "last-admin" = "ok") {
  const cuerpos: Record<string, unknown>[] = [];
  server.use(
    http.patch(`${API}/admin/users/:id`, async ({ request }) => {
      cuerpos.push((await request.json()) as Record<string, unknown>);
      if (respuesta === "last-admin")
        return responder("/admin/users/{id_usuario}", "patch", 409, {
          type: "last-admin",
          title: "Tiene que quedar al menos un administrador activo",
          status: 409,
          trace_id: "t-1",
        });
      return responder("/admin/users/{id_usuario}", "patch", 200, beto);
    }),
  );
  return cuerpos;
}

const montarAdmin = () =>
  montar("/admin/usuarios", [
    [
      "/admin/usuarios",
      <>
        <Encabezado />
        <AdminUsuarios />
      </>,
    ],
    ["/login", <Login />],
  ]);

function entrarComo(u: typeof usuario) {
  useSession.getState().iniciarSesion(u, "token-abc", 3600);
}

describe("acceso", () => {
  test('el enlace "Administración" solo lo ve el admin', async () => {
    entrarComo(admin);
    servirUsuarios();
    const { unmount } = montarAdmin();
    expect(screen.getByRole("link", { name: "Administración" })).toHaveAttribute(
      "href",
      "/admin/usuarios",
    );
    await screen.findByText("beto@mail.com");
    unmount();

    useSession.getState().cerrarSesion();
    entrarComo(usuario);
    montarAdmin();
    expect(screen.queryByRole("link", { name: "Administración" })).not.toBeInTheDocument();
  });

  test("otro usuario ve que no tiene permiso", () => {
    entrarComo(usuario);
    montarAdmin();
    expect(screen.getByText("No tenés permiso para ver esta página")).toBeInTheDocument();
  });

  test("sin sesión va a /login", () => {
    montarAdmin();
    expect(screen.getByLabelText("ubicación")).toHaveTextContent("/login");
  });
});

describe("tabla", () => {
  test("lista nombre, correo, rol, estado e inscripciones activas", async () => {
    entrarComo(admin);
    servirUsuarios();
    montarAdmin();
    const filaBeto = (await screen.findByText("beto@mail.com")).closest("tr") as HTMLElement;
    expect(filaBeto).toHaveTextContent("Beto");
    expect(filaBeto).toHaveTextContent("Activo");
    expect(filaBeto).toHaveTextContent("2");
    expect(within(filaBeto).getByRole("combobox", { name: "Rol de Beto" })).toHaveValue("ATTENDEE");
  });

  test("en su propia fila el admin no ve las acciones de rol ni de desactivar", async () => {
    entrarComo(admin);
    servirUsuarios();
    montarAdmin();
    const propia = (await screen.findByText("admin@mail.com")).closest("tr") as HTMLElement;
    expect(within(propia).queryByRole("combobox")).not.toBeInTheDocument();
    expect(within(propia).queryByRole("button", { name: /Desactivar/ })).not.toBeInTheDocument();
    expect(within(propia).getByRole("button", { name: /Editar nombre/ })).toBeInTheDocument();
  });

  test("el buscador espera 300 ms y manda q; los filtros mandan role e is_active", async () => {
    entrarComo(admin);
    const pedidos = servirUsuarios();
    const user = userEvent.setup();
    montarAdmin();
    await screen.findByText("beto@mail.com");

    await user.type(screen.getByRole("searchbox", { name: "Buscar" }), "ana");
    expect(pedidos.some((p) => p.has("q"))).toBe(false);
    await waitFor(() => expect(pedidos.at(-1)?.get("q")).toBe("ana"));
    expect(pedidos.filter((p) => p.has("q"))).toHaveLength(1);

    await user.selectOptions(screen.getByRole("combobox", { name: "Rol" }), "ORGANIZER");
    await waitFor(() => expect(pedidos.at(-1)?.get("role")).toBe("ORGANIZER"));
    await user.selectOptions(screen.getByRole("combobox", { name: "Estado" }), "false");
    await waitFor(() => expect(pedidos.at(-1)?.get("is_active")).toBe("false"));
  });
});

describe("acciones", () => {
  test("cambiar el rol pide confirmación y sin confirmar no llama a la API", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Rol de Beto" }),
      "ORGANIZER",
    );
    await user.click(
      within(screen.getByRole("alertdialog")).getByRole("button", { name: "Volver" }),
    );
    expect(cuerpos).toHaveLength(0);

    await user.selectOptions(screen.getByRole("combobox", { name: "Rol de Beto" }), "ORGANIZER");
    await user.click(
      within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cambiar rol" }),
    );
    expect(await screen.findByText("Cambiaste el rol de Beto")).toBeInTheDocument();
    expect(cuerpos).toEqual([{ role: "ORGANIZER" }]);
  });

  test("desactivar avisa que se cierra su sesión, pide confirmación y manda is_active", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    await user.click(await screen.findByRole("button", { name: "Desactivar a Beto" }));
    const dialogo = screen.getByRole("alertdialog");
    expect(dialogo).toHaveTextContent("Se va a cerrar su sesión");
    await user.click(within(dialogo).getByRole("button", { name: "Volver" }));
    expect(cuerpos).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Desactivar a Beto" }));
    await user.click(
      within(screen.getByRole("alertdialog")).getByRole("button", { name: "Desactivar" }),
    );
    expect(await screen.findByText("Desactivaste a Beto")).toBeInTheDocument();
    expect(cuerpos).toEqual([{ is_active: false }]);
  });

  test("un 409 last-admin muestra su title", async () => {
    entrarComo(admin);
    servirUsuarios();
    servirPatch("last-admin");
    const user = userEvent.setup();
    montarAdmin();

    await user.click(await screen.findByRole("button", { name: "Desactivar a Beto" }));
    await user.click(
      within(screen.getByRole("alertdialog")).getByRole("button", { name: "Desactivar" }),
    );
    expect(
      await screen.findByText("Tiene que quedar al menos un administrador activo"),
    ).toBeInTheDocument();
  });

  test("editar el nombre manda solo full_name", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    await user.click(await screen.findByRole("button", { name: "Editar nombre de Beto" }));
    const campo = screen.getByRole("textbox", { name: "Nombre" });
    await user.clear(campo);
    await user.type(campo, "Alberto");
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByText("Guardaste el nombre")).toBeInTheDocument();
    expect(cuerpos).toEqual([{ full_name: "Alberto" }]);
  });

  test("un nombre vacío marca el campo con aria-invalid y no llama a la API", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    await user.click(await screen.findByRole("button", { name: "Editar nombre de Beto" }));
    await user.clear(screen.getByRole("textbox", { name: "Nombre" }));
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(screen.getByRole("textbox", { name: "Nombre" })).toHaveAttribute("aria-invalid", "true");
    expect(cuerpos).toHaveLength(0);
  });

  test("reactivar pide confirmación, manda is_active true y avisa", async () => {
    entrarComo(admin);
    servirUsuarios([adminFila, fila({ is_active: false })]);
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    await user.click(await screen.findByRole("button", { name: "Reactivar a Beto" }));
    await user.click(
      within(screen.getByRole("alertdialog")).getByRole("button", { name: "Reactivar" }),
    );
    expect(await screen.findByText("Reactivaste a Beto")).toBeInTheDocument();
    expect(cuerpos).toEqual([{ is_active: true }]);
  });

  test("al editar su propio nombre, el encabezado muestra el nombre nuevo", async () => {
    entrarComo(admin);
    servirUsuarios();
    server.use(
      http.patch(`${API}/admin/users/:id`, async ({ request }) => {
        const { full_name } = (await request.json()) as { full_name: string };
        return responder("/admin/users/{id_usuario}", "patch", 200, { ...adminFila, full_name });
      }),
    );
    const user = userEvent.setup();
    montarAdmin();

    await user.click(await screen.findByRole("button", { name: "Editar nombre de Admin" }));
    const campo = screen.getByRole("textbox", { name: "Nombre" });
    await user.clear(campo);
    await user.type(campo, "Administradora");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByRole("link", { name: "Administradora" })).toHaveAttribute(
      "href",
      "/perfil",
    );
    expect(useSession.getState().user?.full_name).toBe("Administradora");
  });
});
