import { useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import { diaBogota, etiquetaDia, horaBogota } from "../lib/fechas";
import type { Sesion } from "../lib/useSesiones";
import type { Evento } from "../stores/eventos";
import { FormularioSesion } from "./FormularioSesion";
import { Button } from "./ui/Button";
import { DialogoConfirmacion } from "./ui/DialogoConfirmacion";
import { Modal } from "./ui/Modal";
import { Spinner } from "./ui/Spinner";
import { Toast, type ToastProps } from "./ui/Toast";

interface Props {
  cargando: boolean;
  sesiones?: Sesion[];
  error?: ApiError;
  evento: Pick<Evento, "id" | "start_at" | "end_at" | "capacity">;
  /** El dueño del evento o el admin, y el evento todavía admite cambios. */
  puede: boolean;
  /** Se llama con la sesión que el servidor creó o actualizó. */
  onGuardada: (sesion: Sesion) => void;
  /** Se llama cuando el servidor confirmó el borrado. */
  onEliminada: (id: string) => void;
}

function agruparPorDia(sesiones: Sesion[]) {
  const ordenadas = [...sesiones].sort((a, b) => a.start_at.localeCompare(b.start_at));
  const dias = new Map<string, Sesion[]>();
  for (const s of ordenadas) {
    const dia = diaBogota(s.start_at);
    dias.set(dia, [...(dias.get(dia) ?? []), s]);
  }
  return [...dias.entries()];
}

/** `null`: cerrado. `"nueva"`: crear. Una sesión: editarla. */
type Formulario = "nueva" | Sesion | null;

export function SeccionSesiones({
  cargando,
  sesiones,
  error,
  evento,
  puede,
  onGuardada,
  onEliminada,
}: Props) {
  const [formulario, setFormulario] = useState<Formulario>(null);
  const [pendiente, setPendiente] = useState<Sesion | null>(null);
  const [trabajando, setTrabajando] = useState(false);
  const [aviso, setAviso] = useState<Pick<ToastProps, "message" | "tone"> | null>(null);

  async function eliminar(sesion: Sesion) {
    setTrabajando(true);
    try {
      await api<void>(`/sessions/${sesion.id}`, { method: "DELETE" });
      onEliminada(sesion.id);
      setAviso({ message: "Sesión eliminada", tone: "exito" });
    } catch (e) {
      const title = e instanceof ApiError ? e.title : "Ocurrió un error inesperado";
      setAviso({ message: title, tone: "error" });
    } finally {
      setTrabajando(false);
      setPendiente(null);
    }
  }

  return (
    <section aria-labelledby="titulo-sesiones" className="mt-6 flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="titulo-sesiones" className="text-xl font-semibold">
          Sesiones
        </h2>
        {puede && (
          <Button type="button" onClick={() => setFormulario("nueva")}>
            Agregar sesión
          </Button>
        )}
      </div>
      {cargando && (
        <div className="flex justify-center p-6">
          <Spinner />
        </div>
      )}
      {error && (
        <p role="alert" className="text-red-700">
          {error.title}
        </p>
      )}
      {sesiones?.length === 0 && (
        <p className="text-gray-600">Este evento todavía no tiene sesiones</p>
      )}
      {sesiones &&
        agruparPorDia(sesiones).map(([dia, delDia]) => (
          <div key={dia} className="flex flex-col gap-2">
            <h3 className="font-medium text-gray-700 capitalize">
              {etiquetaDia(delDia[0].start_at)}
            </h3>
            <ul className="flex flex-col gap-2">
              {delDia.map((s) => (
                <li key={s.id} className="rounded-md border border-gray-200 p-4">
                  <h4 className="font-semibold">{s.title}</h4>
                  <p>
                    {horaBogota(s.start_at)} a {horaBogota(s.end_at)}
                  </p>
                  {s.room && <p className="text-gray-600">{s.room}</p>}
                  {s.capacity !== null && <p className="text-gray-600">Capacidad: {s.capacity}</p>}
                  {s.speakers.length > 0 && (
                    <p className="text-gray-600">{s.speakers.map((p) => p.full_name).join(", ")}</p>
                  )}
                  {puede && (
                    <div className="mt-2 flex flex-wrap gap-3">
                      <button
                        type="button"
                        aria-label={`Editar sesión ${s.title}`}
                        className="rounded-md border border-gray-300 px-3 py-1"
                        onClick={() => setFormulario(s)}
                      >
                        Editar
                      </button>
                      <Button
                        type="button"
                        aria-label={`Eliminar sesión ${s.title}`}
                        className="bg-red-700 px-3 py-1"
                        onClick={() => setPendiente(s)}
                      >
                        Eliminar
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      {formulario && (
        <Modal
          titulo={formulario === "nueva" ? "Agregar sesión" : "Editar sesión"}
          onCerrar={() => setFormulario(null)}
        >
          <FormularioSesion
            evento={evento}
            sesion={formulario === "nueva" ? undefined : formulario}
            onGuardada={(guardada) => {
              onGuardada(guardada);
              setAviso({
                message: formulario === "nueva" ? "Sesión creada" : "Sesión actualizada",
                tone: "exito",
              });
              setFormulario(null);
            }}
            onCancelar={() => setFormulario(null)}
          />
        </Modal>
      )}
      {pendiente && (
        <DialogoConfirmacion
          titulo="Eliminar la sesión"
          mensaje={`Se borra «${pendiente.title}». No se puede deshacer.`}
          confirmar="Sí, eliminar la sesión"
          cargando={trabajando}
          onConfirmar={() => eliminar(pendiente)}
          onVolver={() => setPendiente(null)}
        />
      )}
      {aviso && (
        <div className="fixed right-4 bottom-4 z-20">
          <Toast {...aviso} onClose={() => setAviso(null)} />
        </div>
      )}
    </section>
  );
}
