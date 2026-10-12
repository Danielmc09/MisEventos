import type { ReactNode } from "react";
import { formatearFecha } from "../lib/fechas";
import { quedan } from "../lib/plural";
import type { components } from "../api/schema";
import type { Evento } from "../stores/eventos";
import { InsigniaEstado } from "./InsigniaEstado";
import { Chip } from "./ui/Chip";
import { Enlace } from "./ui/Enlace";
import { TextoSecundario } from "./ui/TextoSecundario";
import { Tarjeta } from "./ui/Tarjeta";
import { TituloSeccion } from "./ui/TituloSeccion";

type Resumen = components["schemas"]["ResumenEvento"];

interface Props {
  /** Un evento del listado (con cupos) o el resumen que trae una inscripción (sin cupos). */
  evento: Evento | Resumen;
  /** Posición en la lista, para escalonar la entrada. */
  indice?: number;
  /** Lo que cuelga del evento dentro de la misma tarjeta (p. ej. las sesiones reservadas). */
  children?: ReactNode;
}

export function EventoCard({ evento, indice, children }: Props) {
  const conCupos = "available_spots" in evento;
  return (
    <Tarjeta indice={indice}>
      <div className="flex flex-col gap-2">
        <InsigniaEstado
          evento={evento}
          etiquetaCancelado={conCupos ? undefined : "Evento cancelado"}
        />
        <TituloSeccion estilo="tarjeta">
          <Enlace to={`/eventos/${evento.id}`}>{evento.name}</Enlace>
        </TituloSeccion>
      </div>
      <div className="flex flex-col gap-1">
        <TextoSecundario pequeno>
          <time dateTime={evento.start_at}>{formatearFecha(evento.start_at)}</time>
        </TextoSecundario>
        {evento.location && <TextoSecundario pequeno>{evento.location}</TextoSecundario>}
      </div>
      {conCupos && (
        <div className="mt-auto flex flex-wrap gap-2">
          {evento.available_spots === 0 && <Chip tono="error">Sin cupos</Chip>}
          <Chip tono={evento.available_spots === 0 ? "neutro" : "acento"}>
            {quedan(evento.available_spots, "cupo", "cupos")}
          </Chip>
        </div>
      )}
      {children}
    </Tarjeta>
  );
}
