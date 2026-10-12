import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/errors";
import { EventoCard } from "../../components/EventoCard";
import { AlertaError } from "../../components/ui/AlertaError";
import { EstadoVacio } from "../../components/ui/EstadoVacio";
import { ImagenPortada } from "../../components/ui/ImagenPortada";
import { Input } from "../../components/ui/Input";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";
import { Paginacion } from "../../components/ui/Paginacion";
import { Select } from "../../components/ui/Select";
import { Spinner } from "../../components/ui/Spinner";
import { TextoSecundario } from "../../components/ui/TextoSecundario";
import { useEventos, type PaginaEventos } from "../../stores/eventos";
import { useTienePermiso } from "../../stores/session";

/** Filtros de estado del inicio: la clave viaja en la URL (`?estado=`), `status` es lo que pide la API. */
const ESTADOS = {
  publicados: { etiqueta: "Publicados", status: "PUBLISHED", soloBorradores: false },
  cancelados: { etiqueta: "Cancelados", status: "CANCELLED", soloBorradores: false },
  borradores: { etiqueta: "Borradores", status: "DRAFT", soloBorradores: true },
  todos: { etiqueta: "Todos", status: "", soloBorradores: true },
} as const;
type Estado = keyof typeof ESTADOS;

interface Resultado {
  consulta: string;
  pagina?: PaginaEventos;
  error?: string;
}

export default function Inicio() {
  const [params, setParams] = useSearchParams();
  const listar = useEventos((s) => s.listar);
  const veBorradores = useTienePermiso("evento:crear");
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

  const quitarFiltros = () => {
    clearTimeout(temporizador.current);
    setTexto("");
    setParams({});
  };

  // Un valor desconocido o no permitido se trata como "publicados": así lista y select coinciden.
  const pedido = params.get("estado") ?? "";
  const estado: Estado =
    Object.hasOwn(ESTADOS, pedido) && (veBorradores || !ESTADOS[pedido as Estado].soloBorradores)
      ? (pedido as Estado)
      : "publicados";
  const hayFiltros = !!(params.get("q") || estado !== "publicados");

  const irAPagina = (pagina: number) =>
    setParams((previos) => {
      const nuevos = new URLSearchParams(previos);
      if (pagina > 1) nuevos.set("page", String(pagina));
      else nuevos.delete("page");
      return nuevos;
    });

  const consulta = new URLSearchParams(
    [
      ["q", params.get("q")],
      ["status", ESTADOS[estado].status],
      ["page", params.get("page")],
    ].flatMap(([k, v]) => (v ? [[k!, v]] : [])),
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
    <Pagina ancho="ancho">
      <ImagenPortada />
      <div className="flex flex-col gap-1">
        <TituloPagina>Próximos eventos</TituloPagina>
        <TextoSecundario>Encontrá un evento e inscribite en un minuto</TextoSecundario>
      </div>
      <div className="flex flex-wrap items-end gap-4">
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
        <Select
          id="estado"
          label="Estado"
          value={estado}
          onChange={(e) => filtrar("estado", e.target.value === "publicados" ? "" : e.target.value)}
        >
          {(Object.keys(ESTADOS) as Estado[])
            .filter((clave) => veBorradores || !ESTADOS[clave].soloBorradores)
            .map((clave) => (
              <option key={clave} value={clave}>
                {ESTADOS[clave].etiqueta}
              </option>
            ))}
        </Select>
      </div>
      <div className="flex flex-col gap-6">
        {!actual && (
          <div className="flex justify-center p-10">
            <Spinner />
          </div>
        )}
        {actual?.error && <AlertaError title={actual.error} />}
        {actual?.pagina && actual.pagina.items.length === 0 && (
          <EstadoVacio
            mensaje="No hay eventos que coincidan"
            accion={hayFiltros ? "Quitar filtros" : undefined}
            onAccion={hayFiltros ? quitarFiltros : undefined}
          />
        )}
        {actual?.pagina && actual.pagina.items.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {actual.pagina.items.map((e, i) => (
              <EventoCard key={e.id} evento={e} indice={i} />
            ))}
          </div>
        )}
        {actual?.pagina && (
          <Paginacion
            pagina={actual.pagina.page}
            paginas={actual.pagina.pages}
            onCambiar={irAPagina}
          />
        )}
      </div>
    </Pagina>
  );
}
