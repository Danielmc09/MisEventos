import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { setupServer } from "msw/node";
import { useState } from "react";
import type { components } from "../api/schema";
import { API, usuario } from "../test/helpers";
import { responder } from "../test/msw";
import { SelectorPonentes, type PonenteDeSesion } from "./SelectorPonentes";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
afterAll(() => server.close());

const ana: components["schemas"]["PonenteSalida"] = {
  id: "b1b1b1b1-0000-4000-8000-000000000001",
  full_name: "Ana Pérez",
  bio: null,
  created_by: usuario.id,
  created_at: "2026-10-01T12:00:00Z",
  updated_at: "2026-10-01T12:00:00Z",
};

const pagina = (items: (typeof ana)[]) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 20,
  pages: 1,
});

/** Reloj falso solo para setTimeout; el shim de `jest` hace que Testing Library avance el reloj al esperar. */
function relojFalso() {
  vi.stubGlobal("jest", { advanceTimersByTime: vi.advanceTimersByTime });
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
}

function Montado({ inicial = [] }: { inicial?: PonenteDeSesion[] }) {
  const [seleccionados, setSeleccionados] = useState(inicial);
  return <SelectorPonentes seleccionados={seleccionados} onChange={setSeleccionados} />;
}

function espiarBusqueda(items = [ana]) {
  const consultas: (string | null)[] = [];
  server.use(
    http.get(`${API}/speakers`, ({ request }) => {
      consultas.push(new URL(request.url).searchParams.get("q"));
      return responder("/speakers", "get", 200, pagina(items));
    }),
  );
  return consultas;
}

describe("búsqueda con espera", () => {
  test("busca 300 ms después de la última tecla, una sola vez y con lo escrito", async () => {
    relojFalso();
    const consultas = espiarBusqueda();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<Montado />);

    await user.type(screen.getByLabelText("Buscar ponente"), "An");
    await act(() => vi.advanceTimersByTimeAsync(299));
    expect(consultas).toEqual([]);

    await act(() => vi.advanceTimersByTimeAsync(1));
    vi.useRealTimers(); // la respuesta de la red no depende del reloj falso
    await vi.waitFor(() => expect(consultas).toEqual(["An"]));
    expect(await screen.findByRole("button", { name: "Agregar a Ana Pérez" })).toBeInTheDocument();
  });

  test("cada tecla reinicia la espera", async () => {
    relojFalso();
    const consultas = espiarBusqueda();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<Montado />);

    await user.type(screen.getByLabelText("Buscar ponente"), "A");
    await act(() => vi.advanceTimersByTimeAsync(200));
    await user.type(screen.getByLabelText("Buscar ponente"), "n");
    await act(() => vi.advanceTimersByTimeAsync(200));
    expect(consultas).toEqual([]);

    await act(() => vi.advanceTimersByTimeAsync(100));
    vi.useRealTimers();
    await vi.waitFor(() => expect(consultas).toEqual(["An"]));
  });

  test("elegir un resultado lo deja seleccionado y se puede quitar", async () => {
    espiarBusqueda();
    const user = userEvent.setup();
    render(<Montado />);

    await user.type(screen.getByLabelText("Buscar ponente"), "An");
    await user.click(await screen.findByRole("button", { name: "Agregar a Ana Pérez" }));

    expect(screen.getByRole("list", { name: "Ponentes elegidos" })).toHaveTextContent("Ana Pérez");
    expect(screen.queryByRole("button", { name: "Agregar a Ana Pérez" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Quitar a Ana Pérez" }));
    expect(screen.queryByRole("list", { name: "Ponentes elegidos" })).not.toBeInTheDocument();
  });
});

describe("crear un ponente nuevo", () => {
  const rutaPost = `${API}/speakers`;

  test("lo crea con POST, queda seleccionado y no envía el formulario que lo contiene", async () => {
    const cuerpos: unknown[] = [];
    server.use(
      http.post(rutaPost, async ({ request }) => {
        cuerpos.push(await request.json());
        return responder("/speakers", "post", 201, ana);
      }),
    );
    const alEnviar = vi.fn((e: React.FormEvent) => e.preventDefault());
    const user = userEvent.setup();
    render(
      <form onSubmit={alEnviar}>
        <Montado />
      </form>,
    );

    await user.click(screen.getByRole("button", { name: "Crear ponente nuevo" }));
    await user.type(screen.getByLabelText("Nombre del ponente"), "Ana Pérez{Enter}");

    const elegidos = await screen.findByRole("list", { name: "Ponentes elegidos" });
    expect(elegidos).toHaveTextContent("Ana Pérez");
    expect(cuerpos).toEqual([{ full_name: "Ana Pérez" }]);
    expect(alEnviar).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Nombre del ponente")).not.toBeInTheDocument();
  });

  test("un 422 aparece en el campo y no se selecciona nada", async () => {
    server.use(
      http.post(rutaPost, () =>
        responder("/speakers", "post", 422, {
          type: "validation-error",
          title: "Los datos enviados no son válidos",
          status: 422,
          trace_id: "t-7",
          errors: [
            { field: "full_name", message: "El nombre debe tener entre 2 y 120 caracteres" },
          ],
        }),
      ),
    );
    const user = userEvent.setup();
    render(<Montado />);

    await user.click(screen.getByRole("button", { name: "Crear ponente nuevo" }));
    await user.type(screen.getByLabelText("Nombre del ponente"), "A");
    await user.click(screen.getByRole("button", { name: "Guardar ponente" }));

    await vi.waitFor(() =>
      expect(screen.getByLabelText("Nombre del ponente")).toHaveAccessibleDescription(
        "El nombre debe tener entre 2 y 120 caracteres",
      ),
    );
    expect(screen.queryByRole("list", { name: "Ponentes elegidos" })).not.toBeInTheDocument();
  });
});
