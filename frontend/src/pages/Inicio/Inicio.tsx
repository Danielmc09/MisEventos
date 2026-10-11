import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/errors";
import { EventoCard } from "../../components/EventoCard";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { useEventos, type PaginaEventos } from "../../stores/eventos";

interface Resultado {
  consulta: string;
  pagina?: PaginaEventos;
  error?: string;
}

export default function Inicio() {
  const [params, setParams] = useSearchParams();
  const listar = useEventos((s) => s.listar);
  const [resultado, setResultado] = useState<Resultado | null>(null);

  const qUrl = params.get("q") ?? "";
  const [texto, setTexto] = useState(qUrl);
  const [qPrevia, setQPrevia] = useState(qUrl);
  const temporizador = useRef<ReturnType<typeof setTimeout>>(undefined);
  // Si la URL cambia por otro lado (botón "atrás"), el campo la sigue.
  if (qUrl !== qPrevia) {
    setQPrevia(qUrl);
    setTexto(qUrl);
  }
  useEffect(() => () => clearTimeout(temporizador.current), []);

  /** Cambia un filtro en la URL; al cambiar un filtro se vuelve a la página 1. */
  const filtrar = (clave: string, valor: string) =>
    setParams((previos) => {
      const nuevos = new URLSearchParams(previos);
      if (valor) nuevos.set(clave, valor);
      else nuevos.delete(clave);
      nuevos.delete("page");
      return nuevos;
    });

  const buscar = (valor: string) => {
    setTexto(valor);
    clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => filtrar("q", valor), 300);
  };

  const irAPagina = (pagina: number) =>
    setParams((previos) => {
      const nuevos = new URLSearchParams(previos);
      if (pagina > 1) nuevos.set("page", String(pagina));
      else nuevos.delete("page");
      return nuevos;
    });

  const consulta = new URLSearchParams(
    ["q", "status", "page"].flatMap((k) => (params.get(k) ? [[k, params.get(k)!]] : [])),
  ).toString();

  useEffect(() => {
    let vigente = true;
    listar(consulta).then(
      (pagina) => vigente && setResultado({ consulta, pagina }),
      (e) =>
        vigente &&
        setResultado({
          consulta,
          error: e instanceof ApiError ? e.title : "Ocurrió un error inesperado",
        }),
    );
    return () => {
      vigente = false;
    };
  }, [consulta, listar]);

  const actual = resultado?.consulta === consulta ? resultado : null;

  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-bold">Mis Eventos</h1>
      <div className="mt-4 flex flex-wrap items-end gap-4">
        <div className="w-full max-w-md">
          <Input
            type="search"
            label="Buscar eventos"
            value={texto}
            maxLength={100}
            placeholder="Nombre o parte del nombre"
            onChange={(e) => buscar(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="estado" className="text-sm font-medium text-gray-700">
            Estado
          </label>
          <select
            id="estado"
            value={params.get("status") ?? ""}
            onChange={(e) => filtrar("status", e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-2"
          >
            <option value="">Todos</option>
            <option value="PUBLISHED">Publicado</option>
            <option value="DRAFT">Borrador</option>
            <option value="CANCELLED">Cancelado</option>
          </select>
        </div>
      </div>
      <div className="mt-6">
        {!actual && (
          <div className="flex justify-center p-10">
            <Spinner />
          </div>
        )}
        {actual?.error && (
          <p role="alert" className="text-red-700">
            {actual.error}
          </p>
        )}
        {actual?.pagina && actual.pagina.items.length === 0 && (
          <p className="text-gray-600">No hay eventos que coincidan</p>
        )}
        {actual?.pagina && actual.pagina.items.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {actual.pagina.items.map((e) => (
              <EventoCard key={e.id} evento={e} />
            ))}
          </div>
        )}
        {actual?.pagina && actual.pagina.pages > 1 && (
          <nav aria-label="Paginación" className="mt-6 flex items-center justify-center gap-4">
            <Button
              disabled={actual.pagina.page <= 1}
              onClick={() => irAPagina(actual.pagina!.page - 1)}
            >
              Anterior
            </Button>
            <span>
              Página {actual.pagina.page} de {actual.pagina.pages}
            </span>
            <Button
              disabled={actual.pagina.page >= actual.pagina.pages}
              onClick={() => irAPagina(actual.pagina!.page + 1)}
            >
              Siguiente
            </Button>
          </nav>
        )}
      </div>
    </main>
  );
}
