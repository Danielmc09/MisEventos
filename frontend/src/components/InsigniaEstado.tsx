import type { Evento } from "../stores/eventos";
import { Chip, type ChipProps } from "./ui/Chip";

const ESTADOS = {
  PUBLISHED: ["Publicado", "exito"],
  DRAFT: ["Borrador", "neutro"],
  CANCELLED: ["Cancelado", "error"],
} as const satisfies Record<string, readonly [string, ChipProps["tono"]]>;

const FINALIZADO = ["Finalizado", "finalizado"] as const;
const EN_CURSO = ["En curso", "acento"] as const;

interface Props {
  evento: Pick<Evento, "status" | "is_finished" | "start_at">;
  /** Cómo se llama el estado cancelado donde se muestra (por defecto, "Cancelado"). */
  etiquetaCancelado?: string;
}

export function InsigniaEstado({ evento, etiquetaCancelado }: Props) {
  const enCurso =
    evento.status === "PUBLISHED" && !evento.is_finished && new Date(evento.start_at) <= new Date();
  const [estado, tono] = evento.is_finished
    ? FINALIZADO
    : enCurso
      ? EN_CURSO
      : ESTADOS[evento.status];
  return (
    <Chip tono={tono}>
      {evento.status === "CANCELLED" && !evento.is_finished && etiquetaCancelado
        ? etiquetaCancelado
        : estado}
    </Chip>
  );
}
