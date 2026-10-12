import { useEffect, useId, useRef, type ReactNode } from "react";

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
  return (
    <div className="fixed inset-0 z-10 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
        tabIndex={-1}
        onKeyDown={(e) => e.key === "Escape" && onCerrar()}
        className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl"
      >
        <h2 id={id} className="mb-4 text-lg font-semibold">
          {titulo}
        </h2>
        {children}
      </div>
    </div>
  );
}
