import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { components } from "../api/schema";
import { formatearFecha } from "../lib/fechas";
import { palabra } from "../lib/plural";
import { AlertaError } from "./ui/AlertaError";
import { BarraProgreso } from "./ui/BarraProgreso";
import { Insignia } from "./ui/Insignia";
import { Cifra } from "./ui/Cifra";
import { Lista } from "./ui/Lista";
import { Paginacion } from "./ui/Paginacion";
import { Spinner } from "./ui/Spinner";
import { Tabla } from "./ui/Tabla";
import { TextoSecundario } from "./ui/TextoSecundario";
import { TituloSeccion } from "./ui/TituloSeccion";

type Estadisticas = components["schemas"]["EstadisticasSalida"];
type Pagina = components["schemas"]["Pagina_Inscrito_"];

/** Lo que llegó de la API para una consulta, o el título del error. */
interface Resultado<T> {
  clave: string;
  datos?: T;
  error?: string;
}

/**
 * Pide `ruta` y devuelve el resultado solo si es el de la `ruta` actual (mientras tanto, `null`).
 * Cuando cambia `version` vuelve a pedir, y mientras llega lo nuevo deja a la vista lo anterior.
 */
function useConsulta<T>(ruta: string, version: number): Resultado<T> | null {
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
  }, [ruta, version]);
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

function Estadisticas({ eventoId, version }: { eventoId: string; version: number }) {
  const stats = useConsulta<Estadisticas>(`/events/${eventoId}/stats`, version);
  if (!stats) return <Cargando />;
  if (stats.error || !stats.datos) return <AlertaError title={stats.error ?? ""} />;
  const { active, cancelled, occupancy_pct, sessions } = stats.datos;
  return (
    <div className="flex flex-col gap-3">
      <dl className="grid grid-cols-3 gap-4">
        <Cifra etiqueta={palabra(active, "Inscrito", "Inscritos")}>{active}</Cifra>
        <Cifra etiqueta={palabra(cancelled, "Cancelado", "Cancelados")}>{cancelled}</Cifra>
        <Cifra etiqueta="Ocupación">{occupancy_pct.toLocaleString("es-CO")} %</Cifra>
      </dl>
      <BarraProgreso etiqueta="Ocupación" valor={occupancy_pct} />
      {sessions.length > 0 && (
        <div role="group" aria-label="Ocupación por sesión" className="flex flex-col gap-2">
          <TextoSecundario>Ocupación por sesión</TextoSecundario>
          <Lista etiqueta="Sesiones">
            {sessions.map((s) => (
              <li key={s.id} className="flex flex-col gap-1">
                <span>
                  {s.title}: {s.reserved} / {s.capacity}
                </span>
                <BarraProgreso etiqueta={`Ocupación de ${s.title}`} valor={s.occupancy_pct} />
              </li>
            ))}
          </Lista>
        </div>
      )}
    </div>
  );
}

function ListaInscritos({ eventoId, version }: { eventoId: string; version: number }) {
  const [numero, setNumero] = useState(1);
  const lista = useConsulta<Pagina>(`/events/${eventoId}/registrations?page=${numero}`, version);
  if (!lista) return <Cargando />;
  if (lista.error || !lista.datos) return <AlertaError title={lista.error ?? ""} />;
  const { items, page, pages } = lista.datos;
  if (items.length === 0) return <TextoSecundario>Todavía no hay inscritos</TextoSecundario>;
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

/**
 * Para el dueño del evento o el admin: cuánta gente se inscribió y quiénes son.
 * `version` es una señal de que las inscripciones cambiaron (p. ej. `registered_count`).
 */
export function PanelInscripciones({ eventoId, version }: { eventoId: string; version: number }) {
  return (
    <section aria-labelledby="titulo-inscripciones" className="mt-4 flex flex-col gap-4">
      <TituloSeccion id="titulo-inscripciones">Inscripciones</TituloSeccion>
      <Estadisticas eventoId={eventoId} version={version} />
      <ListaInscritos eventoId={eventoId} version={version} />
    </section>
  );
}
