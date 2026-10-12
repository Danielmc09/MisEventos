import type { FormEvent } from "react";
import type { Sesion } from "../lib/useSesiones";
import type { Evento } from "../stores/eventos";
import { SelectorPonentes } from "./SelectorPonentes";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";

export interface FormularioSesionProps {
  evento: Pick<Evento, "id" | "start_at" | "end_at" | "capacity">;
  /** Si viene, el formulario edita esa sesión; si no, crea una. */
  sesion?: Sesion;
  onGuardada: (sesion: Sesion) => void;
  onCancelar: () => void;
}

export function FormularioSesion({ sesion, onCancelar }: FormularioSesionProps) {
  return (
    <form
      onSubmit={(e: FormEvent) => e.preventDefault()}
      noValidate
      className="flex flex-col gap-4"
    >
      <Input label="Título" />
      <Input label="Sala" />
      <Input label="Inicio" type="datetime-local" />
      <Input label="Fin" type="datetime-local" />
      <Input label="Capacidad" type="number" />
      <SelectorPonentes seleccionados={[]} onChange={() => {}} />
      <Button type="submit">{sesion ? "Guardar cambios" : "Crear sesión"}</Button>
      <button type="button" onClick={onCancelar}>
        Cancelar
      </button>
    </form>
  );
}
