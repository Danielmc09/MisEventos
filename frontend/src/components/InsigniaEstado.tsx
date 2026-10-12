import type { Evento } from "../stores/eventos";

const ESTADOS = {
  PUBLISHED: ["Publicado", "bg-green-100 text-green-800"],
  DRAFT: ["Borrador", "bg-gray-100 text-gray-800"],
  CANCELLED: ["Cancelado", "bg-red-100 text-red-800"],
} as const;

const FINALIZADO = ["Finalizado", "bg-amber-100 text-amber-800"] as const;

export function InsigniaEstado({ evento }: { evento: Evento }) {
  const [estado, tono] = evento.is_finished ? FINALIZADO : ESTADOS[evento.status];
  return (
    <span className={`self-start rounded-full px-2 py-0.5 text-xs font-medium ${tono}`}>
      {estado}
    </span>
  );
}
