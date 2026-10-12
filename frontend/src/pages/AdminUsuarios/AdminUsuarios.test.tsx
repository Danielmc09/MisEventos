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

type ErrorPatch = "email-taken" | "last-admin" | "cannot-modify-self";
const TITULOS: Record<ErrorPatch, string> = {
  "email-taken": "Ese correo ya está registrado",
  "last-admin": "Tiene que quedar al menos un administrador activo",
  "cannot-modify-self": "No podés cambiar tu propio rol ni tu estado",
};

function servirPatch(error?: ErrorPatch, base: UsuarioAdmin = beto) {
  const cuerpos: Record<string, unknown>[] = [];
  server.use(
    http.patch(`${API}/admin/users/:id`, async ({ request }) => {
      const cuerpo = (await request.json()) as Record<string, unknown>;
      cuerpos.push(cuerpo);
      if (error)
        return responder("/admin/users/{id_usuario}", "patch", 409, {
          type: error,
          title: TITULOS[error],
          status: 409,
          trace_id: "t-1",
        });
      return responder("/admin/users/{id_usuario}", "patch", 200, { ...base, ...cuerpo });
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
  test('el ítem "Administración" del menú de la cuenta solo lo ve el admin', async () => {
    const user = userEvent.setup();
    entrarComo(admin);
    servirUsuarios();
    const { unmount } = montarAdmin();
    await user.click(screen.getByRole("button", { name: "Menú de la cuenta" }));
    expect(screen.getByRole("menuitem", { name: "Administración" })).toHaveAttribute(
      "href",
      "/admin/usuarios",
    );
    await screen.findByText("beto@mail.com");
    unmount();

    useSession.getState().cerrarSesion();
    entrarComo(usuario);
    montarAdmin();
    await user.click(screen.getByRole("button", { name: "Menú de la cuenta" }));
    expect(screen.getByRole("menuitem", { name: "Mi perfil" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Administración" })).not.toBeInTheDocument();
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
    expect(filaBeto).toHaveTextContent("Asistente");
    expect(within(filaBeto).getByRole("button", { name: "Editar a Beto" })).toBeInTheDocument();
    expect(within(filaBeto).queryByRole("combobox")).not.toBeInTheDocument();
  });

  test("cada fila ofrece un único botón Editar, también la propia", async () => {
    entrarComo(admin);
    servirUsuarios();
    montarAdmin();
    const propia = (await screen.findByText("admin@mail.com")).closest("tr") as HTMLElement;
    expect(within(propia).getByRole("button", { name: "Editar a Admin" })).toBeInTheDocument();
    expect(within(propia).getAllByRole("button")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /Desactivar|Reactivar/ })).not.toBeInTheDocument();
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

describe("pestañas", () => {
  const todos = [
    adminFila,
    fila({ id: "o-1", email: "olga@mail.com", full_name: "Olga", role: "ORGANIZER" }),
    beto,
  ];

  function servirPorRol() {
    const pedidos: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/admin/users`, ({ request }) => {
        const p = new URL(request.url).searchParams;
        pedidos.push(p);
        const roles = p.getAll("role");
        const items = roles.length ? todos.filter((u) => roles.includes(u.role)) : todos;
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

  test("cada pestaña pide su grupo de roles y muestra solo ese grupo", async () => {
    entrarComo(admin);
    const pedidos = servirPorRol();
    const user = userEvent.setup();
    montarAdmin();
    await screen.findByText("beto@mail.com");
    expect(screen.getByRole("tab", { name: "Todos" })).toHaveAttribute("aria-selected", "true");
    expect(pedidos.at(-1)?.has("role")).toBe(false);

    await user.click(screen.getByRole("tab", { name: "Equipo" }));
    await waitFor(() => expect(screen.queryByText("beto@mail.com")).not.toBeInTheDocument());
    expect(pedidos.at(-1)?.getAll("role")).toEqual(["ADMIN", "ORGANIZER"]);
    expect(screen.getByText("olga@mail.com")).toBeInTheDocument();
    expect(screen.getByText("admin@mail.com")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Asistentes" }));
    await screen.findByText("beto@mail.com");
    expect(pedidos.at(-1)?.getAll("role")).toEqual(["ATTENDEE"]);
    expect(screen.queryByText("olga@mail.com")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Todos" }));
    await screen.findByText("olga@mail.com");
    expect(pedidos.at(-1)?.has("role")).toBe(false);
  });

  test("el select de rol filtra dentro de la pestaña y se limpia al cambiar de pestaña", async () => {
    entrarComo(admin);
    const pedidos = servirPorRol();
    const user = userEvent.setup();
    montarAdmin();
    await screen.findByText("beto@mail.com");

    await user.click(screen.getByRole("tab", { name: "Equipo" }));
    const rol = await screen.findByRole("combobox", { name: "Rol" });
    expect(within(rol).queryByRole("option", { name: "Asistente" })).not.toBeInTheDocument();
    await user.selectOptions(rol, "ORGANIZER");
    await waitFor(() => expect(pedidos.at(-1)?.getAll("role")).toEqual(["ORGANIZER"]));

    await user.click(screen.getByRole("tab", { name: "Todos" }));
    await waitFor(() => expect(pedidos.at(-1)?.has("role")).toBe(false));
    expect(screen.getByRole("combobox", { name: "Rol" })).toHaveValue("");
  });

  test("en Asistentes no hay select de rol, porque el grupo ya es un solo rol", async () => {
    entrarComo(admin);
    servirPorRol();
    const user = userEvent.setup();
    montarAdmin();
    await screen.findByText("beto@mail.com");

    await user.click(screen.getByRole("tab", { name: "Asistentes" }));

    await screen.findByText("beto@mail.com");
    expect(screen.queryByRole("combobox", { name: "Rol" })).not.toBeInTheDocument();
  });
});

describe("formulario de edición", () => {
  const abrir = async (user: ReturnType<typeof userEvent.setup>, nombre = "Beto") => {
    await user.click(await screen.findByRole("button", { name: `Editar a ${nombre}` }));
    return within(screen.getByRole("dialog", { name: `Editar a ${nombre}` }));
  };
  const confirmacion = () => within(screen.getByRole("alertdialog"));

  test("abre con los datos de la fila", async () => {
    entrarComo(admin);
    servirUsuarios();
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user);

    expect(form.getByRole("textbox", { name: "Nombre" })).toHaveValue("Beto");
    expect(form.getByRole("textbox", { name: "Correo" })).toHaveValue("beto@mail.com");
    expect(form.getByRole("combobox", { name: "Rol" })).toHaveValue("ATTENDEE");
    expect(form.getByRole("combobox", { name: "Estado" })).toHaveValue("true");
  });

  test("manda solo lo que cambió y avisa", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user);
    const campo = form.getByRole("textbox", { name: "Nombre" });
    await user.clear(campo);
    await user.type(campo, "Alberto");
    await user.click(form.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardaste los cambios de Alberto")).toBeInTheDocument();
    expect(cuerpos).toEqual([{ full_name: "Alberto" }]);
  });

  test("cambiar el correo pide confirmación, sin confirmar no llama a la API y después manda solo email", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user);
    const campo = form.getByRole("textbox", { name: "Correo" });
    await user.clear(campo);
    await user.type(campo, "nuevo@mail.com");
    await user.click(form.getByRole("button", { name: "Guardar" }));
    const dialogo = screen.getByRole("alertdialog");
    expect(dialogo).toHaveTextContent("¿Cambiar el correo de Beto?");
    expect(dialogo).toHaveTextContent("Va a tener que iniciar sesión con el correo nuevo.");
    await user.click(within(dialogo).getByRole("button", { name: "Volver" }));
    expect(cuerpos).toHaveLength(0);

    await user.click(form.getByRole("button", { name: "Guardar" }));
    await user.click(confirmacion().getByRole("button", { name: "Sí, cambiar el correo" }));

    await screen.findByText("Guardaste los cambios de Beto");
    expect(cuerpos).toEqual([{ email: "nuevo@mail.com" }]);
  });

  test("si cambian el correo y el rol, un solo diálogo menciona los dos", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user);
    const campo = form.getByRole("textbox", { name: "Correo" });
    await user.clear(campo);
    await user.type(campo, "nuevo@mail.com");
    await user.selectOptions(form.getByRole("combobox", { name: "Rol" }), "ORGANIZER");
    await user.click(form.getByRole("button", { name: "Guardar" }));

    const dialogo = screen.getByRole("alertdialog");
    expect(dialogo).toHaveTextContent("Va a tener que iniciar sesión con el correo nuevo.");
    expect(dialogo).toHaveTextContent("Va a pasar a ser organizador.");
    expect(cuerpos).toHaveLength(0);
    await user.click(within(dialogo).getByRole("button", { name: /^Sí, / }));

    await screen.findByText("Guardaste los cambios de Beto");
    expect(cuerpos).toEqual([{ email: "nuevo@mail.com", role: "ORGANIZER" }]);
  });

  test("un nombre vacío marca el campo con aria-invalid y no llama a la API", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user);
    await user.clear(form.getByRole("textbox", { name: "Nombre" }));
    await user.click(form.getByRole("button", { name: "Guardar" }));

    expect(form.getByRole("textbox", { name: "Nombre" })).toHaveAttribute("aria-invalid", "true");
    expect(cuerpos).toHaveLength(0);
  });

  test("un usuario sin nombre cambia de rol sin que se mande full_name", async () => {
    entrarComo(admin);
    const sinNombre = fila({ id: "u-2", email: "sin@mail.com", full_name: null });
    servirUsuarios([adminFila, sinNombre]);
    const cuerpos = servirPatch(undefined, sinNombre);
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user, "sin@mail.com");
    expect(form.getByRole("textbox", { name: "Nombre" })).toHaveValue("");
    await user.selectOptions(form.getByRole("combobox", { name: "Rol" }), "ORGANIZER");
    await user.click(form.getByRole("button", { name: "Guardar" }));

    expect(form.getByRole("textbox", { name: "Nombre" })).not.toHaveAttribute("aria-invalid");
    await user.click(confirmacion().getByRole("button", { name: "Cambiar rol" }));

    expect(await screen.findByText("Guardaste los cambios de sin@mail.com")).toBeInTheDocument();
    expect(cuerpos).toEqual([{ role: "ORGANIZER" }]);
  });

  test("en la propia fila rol y estado están deshabilitados y dicen por qué", async () => {
    entrarComo(admin);
    servirUsuarios();
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user, "Admin");

    const aviso = "No podés cambiar tu propio rol ni tu estado";
    expect(form.getByText(aviso)).toBeVisible();
    for (const nombre of ["Rol", "Estado"]) {
      const campo = form.getByRole("combobox", { name: nombre });
      expect(campo).toBeDisabled();
      expect(campo).toHaveAccessibleDescription(aviso);
    }
    expect(form.getByRole("textbox", { name: "Nombre" })).toBeEnabled();
    expect(form.getByRole("textbox", { name: "Correo" })).toBeEnabled();
  });

  test("al editar su propio nombre, el encabezado muestra el nombre nuevo", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch(undefined, adminFila);
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user, "Admin");
    const campo = form.getByRole("textbox", { name: "Nombre" });
    await user.clear(campo);
    await user.type(campo, "Administradora");
    await user.click(form.getByRole("button", { name: "Guardar" }));

    await user.click(screen.getByRole("button", { name: "Menú de la cuenta" }));
    await waitFor(() =>
      expect(within(screen.getByRole("menu")).getByText("Administradora")).toBeVisible(),
    );
    expect(useSession.getState().user?.full_name).toBe("Administradora");
    expect(cuerpos).toEqual([{ full_name: "Administradora" }]);
  });

  test("email-taken marca el campo correo con aria-invalid y su title", async () => {
    entrarComo(admin);
    servirUsuarios();
    servirPatch("email-taken");
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user);
    const campo = form.getByRole("textbox", { name: "Correo" });
    await user.clear(campo);
    await user.type(campo, "ocupado@mail.com");
    await user.click(form.getByRole("button", { name: "Guardar" }));
    await user.click(confirmacion().getByRole("button", { name: "Sí, cambiar el correo" }));

    await waitFor(() => expect(campo).toHaveAttribute("aria-invalid", "true"));
    expect(campo).toHaveAccessibleDescription(TITULOS["email-taken"]);
    expect(screen.queryByText("Guardaste los cambios de Beto")).not.toBeInTheDocument();
  });

  test("cannot-modify-self muestra su title en el formulario", async () => {
    entrarComo(admin);
    servirUsuarios();
    servirPatch("cannot-modify-self");
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user, "Admin");
    await user.type(form.getByRole("textbox", { name: "Nombre" }), "x");
    await user.click(form.getByRole("button", { name: "Guardar" }));

    expect(await form.findByRole("alert")).toHaveTextContent(TITULOS["cannot-modify-self"]);
  });

  test("cambiar el rol pide confirmación y sin confirmar no llama a la API", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user);
    await user.selectOptions(form.getByRole("combobox", { name: "Rol" }), "ORGANIZER");
    await user.click(form.getByRole("button", { name: "Guardar" }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("¿Cambiar el rol de Beto?");
    await user.click(confirmacion().getByRole("button", { name: "Volver" }));
    expect(cuerpos).toHaveLength(0);

    await user.click(form.getByRole("button", { name: "Guardar" }));
    await user.click(confirmacion().getByRole("button", { name: "Cambiar rol" }));

    expect(await screen.findByText("Guardaste los cambios de Beto")).toBeInTheDocument();
    expect(cuerpos).toEqual([{ role: "ORGANIZER" }]);
  });

  test("desactivar pide confirmación con su texto y manda is_active false", async () => {
    entrarComo(admin);
    servirUsuarios();
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user);
    await user.selectOptions(form.getByRole("combobox", { name: "Estado" }), "false");
    await user.click(form.getByRole("button", { name: "Guardar" }));
    const dialogo = screen.getByRole("alertdialog");
    expect(dialogo).toHaveTextContent("¿Desactivar a Beto?");
    expect(dialogo).toHaveTextContent("Se va a cerrar su sesión y no va a poder volver a entrar.");
    await user.click(within(dialogo).getByRole("button", { name: "Volver" }));
    expect(cuerpos).toHaveLength(0);

    await user.click(form.getByRole("button", { name: "Guardar" }));
    await user.click(confirmacion().getByRole("button", { name: "Sí, desactivar" }));

    expect(await screen.findByText("Guardaste los cambios de Beto")).toBeInTheDocument();
    expect(cuerpos).toEqual([{ is_active: false }]);
  });

  test("reactivar confirma con el botón primario, no con el rojo", async () => {
    entrarComo(admin);
    servirUsuarios([adminFila, fila({ is_active: false })]);
    const cuerpos = servirPatch();
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user);
    await user.selectOptions(form.getByRole("combobox", { name: "Estado" }), "true");
    await user.click(form.getByRole("button", { name: "Guardar" }));
    const reactivar = confirmacion().getByRole("button", { name: "Reactivar" });
    expect(reactivar).toHaveClass("bg-primario");
    expect(reactivar).not.toHaveClass("bg-error");

    await user.click(reactivar);
    await screen.findByText("Guardaste los cambios de Beto");
    expect(cuerpos).toEqual([{ is_active: true }]);
  });

  test("un 409 last-admin muestra su title en el formulario, no como aviso", async () => {
    entrarComo(admin);
    servirUsuarios();
    servirPatch("last-admin");
    const user = userEvent.setup();
    montarAdmin();

    const form = await abrir(user);
    await user.selectOptions(form.getByRole("combobox", { name: "Estado" }), "false");
    await user.click(form.getByRole("button", { name: "Guardar" }));
    await user.click(confirmacion().getByRole("button", { name: "Sí, desactivar" }));

    expect(await form.findByRole("alert")).toHaveTextContent(TITULOS["last-admin"]);
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  test("el vacío ofrece Quitar filtros, que limpia búsqueda, rol y estado y vuelve a la página 1", async () => {
    entrarComo(admin);
    const pedidos: URLSearchParams[] = [];
    server.use(
      http.get(`${API}/admin/users`, ({ request }) => {
        const p = new URL(request.url).searchParams;
        pedidos.push(p);
        const filtrado = p.has("q") || p.has("role") || p.has("is_active");
        const items = filtrado ? [] : [adminFila, beto];
        return responder("/admin/users", "get", 200, {
          items,
          total: items.length,
          page: 1,
          page_size: 20,
          pages: 1,
        });
      }),
    );
    const user = userEvent.setup();
    montarAdmin();
    await screen.findByText("beto@mail.com");

    await user.type(screen.getByRole("searchbox", { name: "Buscar" }), "zzz");
    await user.selectOptions(screen.getByRole("combobox", { name: "Rol" }), "ORGANIZER");
    await user.selectOptions(screen.getByRole("combobox", { name: "Estado" }), "false");
    await screen.findByText("No hay usuarios que coincidan con la búsqueda");

    await user.click(screen.getByRole("button", { name: "Quitar filtros" }));

    await screen.findByText("beto@mail.com");
    expect(screen.getByRole("searchbox", { name: "Buscar" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "Rol" })).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "Estado" })).toHaveValue("");
    const ultimo = pedidos.at(-1);
    expect(ultimo?.get("page")).toBe("1");
    expect(ultimo?.has("q")).toBe(false);
    expect(ultimo?.has("role")).toBe(false);
    expect(ultimo?.has("is_active")).toBe(false);
  });
});
