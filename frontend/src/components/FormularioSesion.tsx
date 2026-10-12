import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { aInputBogota, aISOBogota } from "../lib/fechas";
import type { Sesion } from "../lib/useSesiones";
import type { Evento } from "../stores/eventos";
import { SelectorPonentes, type PonenteDeSesion } from "./SelectorPonentes";
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

/** Los valores del formulario, como los espera la API. */
const aCuerpo = (v: Valores, ponentes: PonenteDeSesion[]) => ({
  title: v.title.trim(),
  description: v.description || null,
  room: v.room.trim() || null,
  start_at: aISOBogota(v.start_at),
  end_at: aISOBogota(v.end_at),
  capacity: v.capacity === "" ? null : Number(v.capacity),
  speaker_ids: ponentes.map((p) => p.id),
});

export function FormularioSesion({
  evento,
  sesion,
  onGuardada,
  onCancelar,
}: FormularioSesionProps) {
  const [valores, setValores] = useState<Valores>(VACIO);
  const [ponentes, setPonentes] = useState<PonenteDeSesion[]>([]);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);

  const campo = (name: keyof Valores) => ({
    name,
    value: valores[name],
    error: errores[name],
    onChange: (e: { target: { value: string } }) =>
      setValores((v) => ({ ...v, [name]: e.target.value })),
  });

  async function enviar(e: FormEvent) {
    e.preventDefault();
    const invalidos = validar(valores, evento);
    setErrores(invalidos);
    if (Object.keys(invalidos).length) return;
    setEnviando(true);
    try {
      const guardada = await api<Sesion>(`/events/${evento.id}/sessions`, {
        method: "POST",
        body: JSON.stringify(aCuerpo(valores, ponentes)),
      });
      onGuardada(guardada);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <Input label="Título" {...campo("title")} />
      <Input label="Sala" {...campo("room")} />
      <Input label="Inicio" type="datetime-local" {...campo("start_at")} />
      <Input label="Fin" type="datetime-local" {...campo("end_at")} />
      <Input label="Capacidad" type="number" {...campo("capacity")} />
      <SelectorPonentes seleccionados={ponentes} onChange={setPonentes} />
      <Button type="submit" loading={enviando}>
        {sesion ? "Guardar cambios" : "Crear sesión"}
      </Button>
      <button type="button" onClick={onCancelar}>
        Cancelar
      </button>
    </form>
  );
}
