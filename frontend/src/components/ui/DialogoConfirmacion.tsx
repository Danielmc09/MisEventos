import { useEffect, useId, useLayoutEffect, useRef } from "react";
import { origenDeApertura } from "../../lib/origenApertura";
import { Button } from "./Button";

export interface DialogoConfirmacionProps {
  titulo: string;
  mensaje: string;
  confirmar: string;
  /** `peligro` para lo destructivo; `primario` para lo que se deshace (reactivar). */
  variante?: "primario" | "peligro";
  cargando?: boolean;
  onConfirmar: () => void;
  onVolver: () => void;
}

export function DialogoConfirmacion({
  titulo,
  mensaje,
  confirmar,
  variante = "peligro",
  cargando,
  onConfirmar,
  onVolver,
}: DialogoConfirmacionProps) {
  const id = useId();
  const volver = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  // El foco arranca en la opción segura; Escape cierra.
  useEffect(() => volver.current?.focus(), []);
  // Crece desde el botón que lo abrió, no desde el centro.
  useLayoutEffect(() => {
    if (panel.current) panel.current.style.transformOrigin = origenDeApertura(panel.current);
  }, []);
  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-tinta/50 p-4">
      <div
        ref={panel}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={`${id}-titulo`}
        aria-describedby={`${id}-mensaje`}
        onKeyDown={(e) => e.key === "Escape" && onVolver()}
        className="flex w-full max-w-md flex-col gap-6 rounded-lg bg-panel p-6 shadow-elevada motion-safe:animate-crecer"
      >
        <div className="flex flex-col gap-2">
          <h2 id={`${id}-titulo`} className="text-lg font-bold text-tinta">
            {titulo}
          </h2>
          <p id={`${id}-mensaje`}>{mensaje}</p>
        </div>
        <div className="flex flex-wrap justify-end gap-3">
          <Button ref={volver} type="button" variante="secundario" onClick={onVolver}>
            Volver
          </Button>
          <Button type="button" loading={cargando} onClick={onConfirmar} variante={variante}>
            {confirmar}
          </Button>
        </div>
      </div>
    </div>
  );
}
