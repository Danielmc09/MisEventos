import type { Evento } from "../stores/eventos";

export function EventoCard({ evento }: { evento: Evento }) {
  return <article data-id={evento.id} />;
}
