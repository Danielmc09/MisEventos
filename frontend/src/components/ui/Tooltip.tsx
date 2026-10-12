import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

export interface TooltipProps {
  texto: string;
  children: ReactNode;
}

/** Un rótulo corto sobre el elemento: aparece con el mouse y con el foco del teclado; Escape lo quita; sale debajo, sin tapar lo de arriba. Se dibuja en el body, así ningún ancestro con overflow (una tabla) lo recorta. */
export function Tooltip({ texto, children }: TooltipProps) {
  const [posicion, setPosicion] = useState<{ top: number; left: number }>();
  const ancla = useRef<HTMLSpanElement>(null);
  const visible = posicion !== undefined;
  const colocar = () => {
    const caja = ancla.current?.getBoundingClientRect();
    if (caja) setPosicion({ top: caja.bottom, left: caja.left });
  };
  const ocultar = () => setPosicion(undefined);
  // Escape lo quita aunque el foco esté en otro lado (solo mouse encima).
  useEffect(() => {
    if (!visible) return;
    const alTeclear = (e: globalThis.KeyboardEvent) => e.key === "Escape" && ocultar();
    document.addEventListener("keydown", alTeclear);
    // Con la posición fija, un scroll la dejaría desfasada: se recalcula. (El Tab que revela un botón fuera de vista también hace scroll.)
    document.addEventListener("scroll", colocar, true);
    return () => {
      document.removeEventListener("keydown", alTeclear);
      document.removeEventListener("scroll", colocar, true);
    };
  }, [visible]);
  return (
    <span
      ref={ancla}
      className="inline-flex"
      onMouseEnter={colocar}
      onMouseLeave={ocultar}
      onFocus={colocar}
      onBlur={ocultar}
    >
      {children}
      {visible &&
        createPortal(
          // El relleno (pt-1) une el botón con el rótulo: el mouse puede cruzar sin que se cierre.
          <span
            role="tooltip"
            style={posicion}
            className="max-md:hidden fixed z-20 pt-1 text-xs font-semibold whitespace-nowrap"
          >
            <span className="block rounded-md bg-tinta px-2 py-1 text-panel shadow-elevada">
              {texto}
            </span>
          </span>,
          document.body,
        )}
    </span>
  );
}
