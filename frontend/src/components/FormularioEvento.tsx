import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { errorDeFormulario } from "../lib/errores";
import { aInputBogota, aISOBogota } from "../lib/fechas";
import { useEventos, type Evento } from "../stores/eventos";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";

const VACIO = { name: "", description: "", location: "", start_at: "", end_at: "", capacity: "" };
type Valores = typeof VACIO;

function validar(v: Valores): Record<string, string> {
  const errores: Record<string, string> = {};
  const nombre = v.name.trim();
  if (nombre.length < 3 || nombre.length > 150)
    errores.name = "El nombre debe tener entre 3 y 150 caracteres";
  if (v.description.length > 5000)
    errores.description = "La descripción admite hasta 5000 caracteres";
  if (v.location.length > 200) errores.location = "El lugar admite hasta 200 caracteres";
  if (!v.start_at) errores.start_at = "Indicá cuándo empieza";
  if (!v.end_at) errores.end_at = "Indicá cuándo termina";
  else if (v.start_at && v.end_at <= v.start_at)
    errores.end_at = "La fecha de fin tiene que ser posterior al inicio";
  const capacidad = Number(v.capacity);
  if (!Number.isInteger(capacidad) || capacidad < 1 || capacidad > 100000)
    errores.capacity = "La capacidad debe ser un número entre 1 y 100000";
  return errores;
}

const desdeEvento = (e: Evento): Valores => ({
  name: e.name,
  description: e.description ?? "",
  location: e.location ?? "",
  start_at: aInputBogota(e.start_at),
  end_at: aInputBogota(e.end_at),
  capacity: String(e.capacity),
});

/** Los valores del formulario, como los espera la API. */
const aCuerpo = (v: Valores) => ({
  name: v.name.trim(),
  description: v.description || null,
  location: v.location || null,
  start_at: aISOBogota(v.start_at),
  end_at: aISOBogota(v.end_at),
  capacity: Number(v.capacity),
});

export function FormularioEvento({ evento }: { evento?: Evento }) {
  const navigate = useNavigate();
  const invalidar = useEventos((s) => s.invalidar);
  const [valores, setValores] = useState<Valores>(evento ? desdeEvento(evento) : VACIO);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [general, setGeneral] = useState<string | null>(null);
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
    const invalidos = validar(valores);
    setErrores(invalidos);
    if (Object.keys(invalidos).length) return;
    setGeneral(null);
    setEnviando(true);
    try {
      let id = evento?.id;
      if (!evento) {
        const creado = await api<Evento>("/events", {
          method: "POST",
          body: JSON.stringify(aCuerpo(valores)),
        });
        id = creado.id;
      } else {
        // PATCH: solo lo que cambió.
        const antes = desdeEvento(evento);
        const nuevo = aCuerpo(valores);
        const cambios = Object.fromEntries(
          (Object.keys(antes) as (keyof Valores)[])
            .filter((k) => antes[k] !== valores[k])
            .map((k) => [k, nuevo[k]]),
        );
        if (Object.keys(cambios).length)
          await api<Evento>(`/events/${evento.id}`, {
            method: "PATCH",
            body: JSON.stringify(cambios),
          });
      }
      invalidar();
      navigate(`/eventos/${id}`);
    } catch (e) {
      const { campos, general } = errorDeFormulario(e);
      setErrores(campos);
      setGeneral(general);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="mt-4 flex flex-col gap-4">
      <Input label="Nombre" {...campo("name")} />
      <div className="flex flex-col gap-1">
        <label htmlFor="descripcion" className="text-sm font-medium text-gray-700">
          Descripción
        </label>
        <textarea
          id="descripcion"
          rows={4}
          className="rounded-md border border-gray-300 px-3 py-2"
          {...{ ...campo("description"), error: undefined }}
        />
      </div>
      <Input label="Lugar" {...campo("location")} />
      <Input label="Inicio" type="datetime-local" {...campo("start_at")} />
      <Input label="Fin" type="datetime-local" {...campo("end_at")} />
      <Input label="Capacidad" type="number" {...campo("capacity")} />
      {general && (
        <p role="alert" className="text-red-700">
          {general}
        </p>
      )}
      <Button type="submit" loading={enviando} className="self-start">
        {evento ? "Guardar cambios" : "Crear evento"}
      </Button>
    </form>
  );
}
