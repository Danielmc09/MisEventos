import type { ReactNode } from "react";
import { diaMesBogota, formatearFecha } from "../lib/fechas";
import { claseGradiente } from "../lib/gradiente";
import type { components } from "../api/schema";
import type { Evento } from "../stores/eventos";
import { ChipCupos } from "./ChipCupos";
import { InsigniaEstado } from "./InsigniaEstado";
import { Enlace } from "./ui/Enlace";
import { FranjaFecha } from "./ui/FranjaFecha";
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
  const { dia, mes } = diaMesBogota(evento.start_at);
  return (
    <Tarjeta
      indice={indice}
      cabecera={
        <FranjaFecha dia={dia} mes={mes} gradiente={claseGradiente(evento.name)}>
          <InsigniaEstado
            evento={evento}
            etiquetaCancelado={conCupos ? undefined : "Evento cancelado"}
          />
        </FranjaFecha>
      }
    >
      <TituloSeccion estilo="tarjeta">
        <Enlace to={`/eventos/${evento.id}`} variante="tarjeta">
          {evento.name}
        </Enlace>
      </TituloSeccion>
      <div className="flex flex-col gap-1">
        <TextoSecundario pequeno>
          <time dateTime={evento.start_at}>{formatearFecha(evento.start_at)}</time>
        </TextoSecundario>
        {evento.location && <TextoSecundario pequeno>{evento.location}</TextoSecundario>}
      </div>
      {conCupos && evento.status === "PUBLISHED" && !evento.is_finished && (
        <div className="mt-auto">
          <ChipCupos capacidad={evento.capacity} libres={evento.available_spots} />
        </div>
      )}
      {/* Por encima del área clickeable del título: lo que cuelga tiene sus propios controles. */}
      {children && <div className="relative">{children}</div>}
    </Tarjeta>
  );
}
