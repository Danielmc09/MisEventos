import type { Evento } from "../stores/eventos";

const ESTADOS = {
  PUBLISHED: ["Publicado", "bg-green-100 text-green-800"],
  DRAFT: ["Borrador", "bg-gray-100 text-gray-800"],
  CANCELLED: ["Cancelado", "bg-red-100 text-red-800"],
} as const;

const FINALIZADO = ["Finalizado", "bg-amber-100 text-amber-800"] as const;
const EN_CURSO = ["En curso", "bg-blue-100 text-blue-800"] as const;

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
    <span className={`self-start rounded-full px-2 py-0.5 text-xs font-medium ${tono}`}>
      {evento.status === "CANCELLED" && !evento.is_finished && etiquetaCancelado
        ? etiquetaCancelado
        : estado}
    </span>
  );
}
