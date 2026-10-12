import { useEffect, useId, useLayoutEffect, useRef, type ReactNode } from "react";
import { origenDeApertura } from "../../lib/origenApertura";

export interface ModalProps {
  titulo: string;
  children: ReactNode;
  onCerrar: () => void;
}

/** Diálogo modal para un formulario: Escape cierra y el foco arranca dentro. */
export function Modal({ titulo, children, onCerrar }: ModalProps) {
  const id = useId();
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => panel.current?.focus(), []);
  // Crece desde el botón que lo abrió, no desde el centro.
  useLayoutEffect(() => {
    if (panel.current) panel.current.style.transformOrigin = origenDeApertura(panel.current);
  }, []);
  return (
    <div className="fixed inset-0 z-10 flex items-start justify-center overflow-y-auto bg-tinta/50 p-4">
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
        tabIndex={-1}
        onKeyDown={(e) => e.key === "Escape" && onCerrar()}
        className="w-full max-w-lg rounded-lg bg-panel p-6 shadow-elevada motion-safe:animate-crecer"
      >
        <h2 id={id} className="mb-6 text-lg font-bold text-tinta">
          {titulo}
        </h2>
        {children}
      </div>
    </div>
  );
}
