import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { components } from "../api/schema";
import { formatearFecha } from "../lib/fechas";
import { AlertaError } from "./ui/AlertaError";
import { BarraProgreso } from "./ui/BarraProgreso";
import { Insignia } from "./ui/Insignia";
import { Paginacion } from "./ui/Paginacion";
import { Spinner } from "./ui/Spinner";
import { Tabla } from "./ui/Tabla";

type Estadisticas = components["schemas"]["EstadisticasSalida"];
type Pagina = components["schemas"]["Pagina_Inscrito_"];

/** Lo que llegó de la API para una consulta, o el título del error. */
interface Resultado<T> {
  clave: string;
  datos?: T;
  error?: string;
}

/** Pide `ruta` y devuelve el resultado solo si es el de la `ruta` actual (mientras tanto, `null`). */
function useConsulta<T>(ruta: string): Resultado<T> | null {
  const [resultado, setResultado] = useState<Resultado<T> | null>(null);
  useEffect(() => {
    let vigente = true;
    api<T>(ruta).then(
      (datos) => vigente && setResultado({ clave: ruta, datos }),
      (e) =>
        vigente &&
        setResultado({
          clave: ruta,
          error: e instanceof ApiError ? e.title : "Ocurrió un error inesperado",
        }),
    );
    return () => {
      vigente = false;
    };
  }, [ruta]);
  return resultado?.clave === ruta ? resultado : null;
}

const ESTADOS = {
  ACTIVE: { texto: "Activa", tono: "exito" },
  CANCELLED: { texto: "Cancelada", tono: "neutro" },
} as const;

function Cargando() {
  return (
    <div className="flex justify-center p-6">
      <Spinner />
    </div>
  );
}

function Estadisticas({ eventoId }: { eventoId: string }) {
  const stats = useConsulta<Estadisticas>(`/events/${eventoId}/stats`);
  if (!stats) return <Cargando />;
  if (stats.error || !stats.datos) return <AlertaError title={stats.error ?? ""} />;
  const { active, cancelled, occupancy_pct } = stats.datos;
  return (
    <div className="flex flex-col gap-3">
      <dl className="grid grid-cols-3 gap-4">
        <div>
          <dt className="text-sm text-gray-600">Inscritos</dt>
          <dd className="text-2xl font-semibold">{active}</dd>
        </div>
        <div>
          <dt className="text-sm text-gray-600">Cancelados</dt>
          <dd className="text-2xl font-semibold">{cancelled}</dd>
        </div>
        <div>
          <dt className="text-sm text-gray-600">Ocupación</dt>
          <dd className="text-2xl font-semibold">{occupancy_pct.toLocaleString("es-CO")} %</dd>
        </div>
      </dl>
      <BarraProgreso etiqueta="Ocupación" valor={occupancy_pct} />
    </div>
  );
}

function ListaInscritos({ eventoId }: { eventoId: string }) {
  const [numero, setNumero] = useState(1);
  const lista = useConsulta<Pagina>(`/events/${eventoId}/registrations?page=${numero}`);
  if (!lista) return <Cargando />;
  if (lista.error || !lista.datos) return <AlertaError title={lista.error ?? ""} />;
  const { items, page, pages } = lista.datos;
  if (items.length === 0) return <p className="text-gray-600">Todavía no hay inscritos</p>;
  return (
    <>
      <Tabla
        descripcion="Lista de inscritos"
        columnas={["Nombre", "Correo", "Estado", "Inscripción"]}
        filas={items.map((i) => ({
          // El correo solo no alcanza: quien se inscribe, cancela y vuelve a inscribirse figura dos veces.
          id: `${i.email}|${i.created_at}`,
          celdas: [
            i.full_name ?? "—",
            i.email,
            <Insignia key="estado" tono={ESTADOS[i.status].tono}>
              {ESTADOS[i.status].texto}
            </Insignia>,
            <time key="fecha" dateTime={i.created_at}>
              {formatearFecha(i.created_at)}
            </time>,
          ],
        }))}
      />
      <Paginacion pagina={page} paginas={pages} onCambiar={setNumero} />
    </>
  );
}

/** Para el dueño del evento o el admin: cuánta gente se inscribió y quiénes son. */
export function PanelInscripciones({ eventoId }: { eventoId: string }) {
  return (
    <section aria-labelledby="titulo-inscripciones" className="mt-4 flex flex-col gap-4">
      <h2 id="titulo-inscripciones" className="text-xl font-semibold">
        Inscripciones
      </h2>
      <Estadisticas eventoId={eventoId} />
      <ListaInscritos eventoId={eventoId} />
    </section>
  );
}
