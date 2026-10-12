import { useState, type FormEvent } from "react";
import { aInputBogota } from "../lib/fechas";
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

const VACIO = { title: "", description: "", room: "", start_at: "", end_at: "", capacity: "" };
type Valores = typeof VACIO;

function validar(v: Valores, evento: FormularioSesionProps["evento"]): Record<string, string> {
  const errores: Record<string, string> = {};
  const titulo = v.title.trim();
  if (titulo.length < 3 || titulo.length > 150)
    errores.title = "El título debe tener entre 3 y 150 caracteres";
  if (v.description.length > 2000)
    errores.description = "La descripción admite hasta 2000 caracteres";
  if (v.room.length > 80) errores.room = "La sala admite hasta 80 caracteres";
  if (!v.start_at) errores.start_at = "Indicá cuándo empieza";
  if (!v.end_at) errores.end_at = "Indicá cuándo termina";
  else if (v.start_at && v.end_at <= v.start_at)
    errores.end_at = "La fecha de fin tiene que ser posterior al inicio";
  // Los valores del formulario y los del evento están en hora de Bogotá, así que se comparan como texto.
  const dentro = "La sesión tiene que caer dentro del horario del evento";
  if (v.start_at && v.start_at < aInputBogota(evento.start_at)) errores.start_at = dentro;
  if (v.end_at && !errores.end_at && v.end_at > aInputBogota(evento.end_at))
    errores.end_at = dentro;
  if (v.capacity !== "") {
    const capacidad = Number(v.capacity);
    if (!Number.isInteger(capacidad) || capacidad < 1 || capacidad > evento.capacity)
      errores.capacity = `La capacidad debe ser un número entre 1 y ${evento.capacity}`;
  }
  return errores;
}

export function FormularioSesion({ evento, sesion, onCancelar }: FormularioSesionProps) {
  const [valores, setValores] = useState<Valores>(VACIO);
  const [errores, setErrores] = useState<Record<string, string>>({});

  const campo = (name: keyof Valores) => ({
    name,
    value: valores[name],
    error: errores[name],
    onChange: (e: { target: { value: string } }) =>
      setValores((v) => ({ ...v, [name]: e.target.value })),
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    setErrores(validar(valores, evento));
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <Input label="Título" {...campo("title")} />
      <Input label="Sala" {...campo("room")} />
      <Input label="Inicio" type="datetime-local" {...campo("start_at")} />
      <Input label="Fin" type="datetime-local" {...campo("end_at")} />
      <Input label="Capacidad" type="number" {...campo("capacity")} />
      <SelectorPonentes seleccionados={[]} onChange={() => {}} />
      <Button type="submit">{sesion ? "Guardar cambios" : "Crear sesión"}</Button>
      <button type="button" onClick={onCancelar}>
        Cancelar
      </button>
    </form>
  );
}
