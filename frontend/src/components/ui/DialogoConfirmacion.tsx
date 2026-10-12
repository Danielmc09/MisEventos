import { useEffect, useId, useRef } from "react";
import { Button } from "./Button";

export interface DialogoConfirmacionProps {
  titulo: string;
  mensaje: string;
  confirmar: string;
  cargando?: boolean;
  onConfirmar: () => void;
  onVolver: () => void;
}

export function DialogoConfirmacion({
  titulo,
  mensaje,
  confirmar,
  cargando,
  onConfirmar,
  onVolver,
}: DialogoConfirmacionProps) {
  const id = useId();
  const volver = useRef<HTMLButtonElement>(null);
  // El foco arranca en la opción segura; Escape cierra.
  useEffect(() => volver.current?.focus(), []);
  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/50 p-4">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={`${id}-titulo`}
        aria-describedby={`${id}-mensaje`}
        onKeyDown={(e) => e.key === "Escape" && onVolver()}
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
      >
        <h2 id={`${id}-titulo`} className="text-lg font-semibold">
          {titulo}
        </h2>
        <p id={`${id}-mensaje`} className="mt-2 text-gray-700">
          {mensaje}
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button ref={volver} type="button" variante="secundario" onClick={onVolver}>
            Volver
          </Button>
          <Button type="button" loading={cargando} onClick={onConfirmar} variante="peligro">
            {confirmar}
          </Button>
        </div>
      </div>
    </div>
  );
}
