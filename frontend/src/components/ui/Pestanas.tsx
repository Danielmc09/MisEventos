import { useRef, type KeyboardEvent, type ReactNode } from "react";

export interface PestanasProps {
  etiqueta: string;
  pestanas: { id: string; titulo: string }[];
  activa: string;
  onCambiar: (id: string) => void;
  /** El contenido del panel de la pestaña activa. */
  children: ReactNode;
}

export function Pestanas({ etiqueta, pestanas, activa, onCambiar, children }: PestanasProps) {
  const botones = useRef<Record<string, HTMLButtonElement | null>>({});

  function moverConFlechas(e: KeyboardEvent, indice: number) {
    const paso = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!paso) return;
    e.preventDefault();
    const destino = pestanas[(indice + paso + pestanas.length) % pestanas.length];
    onCambiar(destino.id);
    botones.current[destino.id]?.focus();
  }

  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" aria-label={etiqueta} className="flex gap-1 border-b border-gray-200">
        {pestanas.map((p, i) => {
          const seleccionada = p.id === activa;
          return (
            <button
              key={p.id}
              ref={(el) => {
                botones.current[p.id] = el;
              }}
              type="button"
              role="tab"
              id={`pestana-${p.id}`}
              aria-selected={seleccionada}
              aria-controls={`panel-${p.id}`}
              tabIndex={seleccionada ? 0 : -1}
              onClick={() => onCambiar(p.id)}
              onKeyDown={(e) => moverConFlechas(e, i)}
              className={`-mb-px border-b-2 px-4 py-2 font-medium focus-visible:outline-2 focus-visible:outline-indigo-600 ${
                seleccionada
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-gray-600 hover:text-gray-900"
              }`}
            >
              {p.titulo}
            </button>
          );
        })}
      </div>
      <div role="tabpanel" id={`panel-${activa}`} aria-labelledby={`pestana-${activa}`}>
        {children}
      </div>
    </div>
  );
}
