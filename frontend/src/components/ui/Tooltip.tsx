import { useEffect, useState, type ReactNode } from "react";

export interface TooltipProps {
  texto: string;
  children: ReactNode;
}

/** Un rótulo corto sobre el elemento: aparece con el mouse y con el foco del teclado; Escape lo quita; sale debajo, sin tapar lo de arriba. */
export function Tooltip({ texto, children }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  // Escape lo quita aunque el foco esté en otro lado (solo mouse encima).
  useEffect(() => {
    if (!visible) return;
    const alTeclear = (e: globalThis.KeyboardEvent) => e.key === "Escape" && setVisible(false);
    document.addEventListener("keydown", alTeclear);
    return () => document.removeEventListener("keydown", alTeclear);
  }, [visible]);
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && (
        // El relleno (pt-1) une el botón con el rótulo: el mouse puede cruzar sin que se cierre.
        <span
          role="tooltip"
          className="max-md:hidden absolute top-full left-0 z-20 pt-1 text-xs font-semibold whitespace-nowrap"
        >
          <span className="block rounded-md bg-tinta px-2 py-1 text-panel shadow-elevada">
            {texto}
          </span>
        </span>
      )}
    </span>
  );
}
