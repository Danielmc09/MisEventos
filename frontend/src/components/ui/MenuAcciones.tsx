import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { BASE_BOTON, VARIANTES_BOTON } from "./estilosBoton";
import { IconoPuntos } from "./iconos/IconoPuntos";

export interface ItemMenu {
  texto: string;
  /** Una acción. */
  onSelect?: () => void;
  /** Una navegación: la opción es un enlace. */
  to?: string;
  /** Una acción destructiva: el texto va en tono de peligro. */
  peligro?: boolean;
}

export interface MenuAccionesProps {
  /** Nombre accesible del botón que abre el menú. */
  etiqueta: string;
  items: ItemMenu[];
  /** Un texto al comienzo del menú, que no es una opción. */
  titulo?: string;
  /** `boton`: «⋯» + el texto de `children`. `circulo`: `children` (una inicial) dentro de un círculo. */
  variante?: "boton" | "circulo";
  /** De qué borde del botón sale el menú. */
  alinear?: "inicio" | "fin";
  deshabilitado?: boolean;
  children: ReactNode;
}

const BOTON = {
  boton: `${BASE_BOTON} ${VARIANTES_BOTON.secundario} pr-4 pl-3`,
  circulo:
    "inline-flex h-11 w-11 items-center justify-center rounded-full bg-primario font-bold text-panel hover:bg-primario-hover focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-foco md:h-10 md:w-10 motion-safe:transition-[background-color,transform] motion-safe:duration-100 motion-safe:active:scale-97",
} as const;

const ITEM =
  "flex min-h-11 w-full items-center px-4 py-2 text-left font-medium hover:bg-fondo focus-visible:bg-fondo focus-visible:-outline-offset-3 focus-visible:outline-3 focus-visible:outline-foco md:min-h-10";

/** Menú de botón (patrón «menu button»): flechas, Inicio/Fin, Escape devuelve el foco, crece desde su botón. */
export function MenuAcciones({
  etiqueta,
  items,
  titulo,
  variante = "boton",
  alinear = "inicio",
  deshabilitado,
  children,
}: MenuAccionesProps) {
  const id = useId();
  const [abierto, setAbierto] = useState(false);
  const [foco, setFoco] = useState<"primero" | "ultimo">("primero");
  const raiz = useRef<HTMLDivElement>(null);
  const disparador = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);

  const opciones = () =>
    Array.from(menu.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);

  useEffect(() => {
    if (!abierto) return;
    const o = opciones();
    (foco === "primero" ? o[0] : o[o.length - 1])?.focus();
  }, [abierto, foco]);

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => {
      if (!raiz.current?.contains(e.target as Node)) setAbierto(false);
    };
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);

  function alTeclearEnDisparador(e: KeyboardEvent) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    setFoco(e.key === "ArrowDown" ? "primero" : "ultimo");
    setAbierto(true);
  }

  function alTeclearEnMenu(e: KeyboardEvent) {
    const o = opciones();
    const i = o.indexOf(document.activeElement as HTMLElement);
    const mover = (destino: number) => {
      e.preventDefault();
      o[(destino + o.length) % o.length]?.focus();
    };
    if (e.key === "ArrowDown") mover(i + 1);
    else if (e.key === "ArrowUp") mover(i - 1);
    else if (e.key === "Home") mover(0);
    else if (e.key === "End") mover(o.length - 1);
    else if (e.key === "Escape") {
      e.stopPropagation();
      setAbierto(false);
      disparador.current?.focus();
    } else if (e.key === "Tab") setAbierto(false);
    else if (e.key === " " && document.activeElement instanceof HTMLAnchorElement) {
      e.preventDefault();
      document.activeElement.click();
    }
  }

  function elegir(item: ItemMenu) {
    setAbierto(false);
    // El foco vuelve al botón antes de que la acción abra, por ejemplo, un diálogo.
    if (!item.to) disparador.current?.focus();
    item.onSelect?.();
  }

  return (
    <div ref={raiz} className="relative inline-flex">
      <button
        ref={disparador}
        type="button"
        aria-label={etiqueta}
        aria-haspopup="menu"
        aria-expanded={abierto}
        aria-controls={abierto ? id : undefined}
        disabled={deshabilitado}
        onClick={() => {
          setFoco("primero");
          setAbierto(!abierto);
        }}
        onKeyDown={alTeclearEnDisparador}
        className={`${BOTON[variante]} disabled:cursor-not-allowed disabled:opacity-60`}
      >
        {variante === "boton" && <IconoPuntos />}
        {children}
      </button>
      {abierto && (
        <div
          ref={menu}
          id={id}
          role="menu"
          aria-label={etiqueta}
          onKeyDown={alTeclearEnMenu}
          className={`absolute top-full z-20 mt-2 flex min-w-48 flex-col overflow-hidden rounded-lg bg-panel py-1 shadow-elevada motion-safe:animate-crecer ${
            alinear === "fin" ? "right-0 origin-top-right" : "left-0 origin-top-left"
          }`}
        >
          {titulo && (
            <p
              role="presentation"
              className="truncate border-b border-borde px-4 py-2 text-sm font-semibold text-texto-suave"
            >
              {titulo}
            </p>
          )}
          {items.map((item) => {
            const clases = `${ITEM} ${item.peligro ? "text-error" : "text-texto"}`;
            return item.to ? (
              <Link
                key={item.texto}
                to={item.to}
                role="menuitem"
                tabIndex={-1}
                className={clases}
                onClick={() => elegir(item)}
              >
                {item.texto}
              </Link>
            ) : (
              <button
                key={item.texto}
                type="button"
                role="menuitem"
                tabIndex={-1}
                className={clases}
                onClick={() => elegir(item)}
              >
                {item.texto}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
