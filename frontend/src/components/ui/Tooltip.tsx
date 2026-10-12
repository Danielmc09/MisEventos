import { useState, type ReactNode } from "react";

export interface TooltipProps {
  texto: string;
  children: ReactNode;
}

/** Un rótulo corto sobre el elemento: aparece con el mouse y con el foco del teclado; Escape lo quita. */
export function Tooltip({ texto, children }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
      onKeyDown={(e) => e.key === "Escape" && setVisible(false)}
    >
      {children}
      {visible && (
        <span
          role="tooltip"
          className="pointer-events-none max-md:hidden absolute bottom-full left-1/2 z-20 mb-1 -translate-x-1/2 rounded-md bg-tinta px-2 py-1 text-xs font-semibold whitespace-nowrap text-panel shadow-elevada"
        >
          {texto}
        </span>
      )}
    </span>
  );
}
