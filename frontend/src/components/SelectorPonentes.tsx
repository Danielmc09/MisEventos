import type { components } from "../api/schema";
import { Input } from "./ui/Input";

export type PonenteDeSesion = components["schemas"]["PonenteDeSesion"];

interface Props {
  seleccionados: PonenteDeSesion[];
  onChange: (ponentes: PonenteDeSesion[]) => void;
}

export function SelectorPonentes({ seleccionados }: Props) {
  return <Input label="Buscar ponente" data-seleccionados={seleccionados.length} />;
}
