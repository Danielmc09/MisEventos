import {
  Fragment,
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";
import { BotonIcono } from "./BotonIcono";
import { BASE_BOTON, VARIANTES_BOTON } from "./estilosBoton";
import { IconoPuntos } from "./iconos/IconoPuntos";
import { Spinner } from "./Spinner";

export interface ItemMenu {
  texto: string;
  /** Una acción. */
  onSelect?: () => void;
  /** Una navegación: la opción es un enlace. */
  to?: string;
  /** Una acción destructiva: el texto va en tono de peligro. */
  peligro?: boolean;
  /** Una línea fina encima, para apartar la opción del resto (por ejemplo, «Cerrar sesión»). */
  separado?: boolean;
}

export interface MenuAccionesProps {
  /** Nombre accesible del botón que abre el menú. */
  etiqueta: string;
  items: ItemMenu[];
  /** Un texto al comienzo del menú, que no es una opción. */
  titulo?: string;
  /** Una segunda línea, más suave, debajo del título (por ejemplo, el email). */
  subtitulo?: string;
  /**
   * `boton`: «⋯» + el texto de `children`. `circulo`: `children` (una inicial) dentro de un círculo.
   * `icono`: un botón cuadrado con «⋯»; `children` es el texto de su tooltip.
   */
  variante?: "boton" | "circulo" | "icono";
  /** De qué borde del botón sale el menú. */
  alinear?: "inicio" | "fin";
  /** Hay una acción en curso: el botón sigue enfocable (no pierde el foco), muestra un spinner y no abre. */
  ocupado?: boolean;
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
  subtitulo,
  variante = "boton",
  alinear = "inicio",
  ocupado,
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
    if (ocupado) return;
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

  const propsDisparador = {
    ref: disparador,
    "aria-haspopup": "menu" as const,
    "aria-expanded": abierto,
    "aria-controls": abierto ? id : undefined,
    "aria-disabled": ocupado || undefined,
    "aria-busy": ocupado || undefined,
    onClick: () => {
      if (ocupado) return;
      setFoco("primero");
      setAbierto(!abierto);
    },
    onKeyDown: alTeclearEnDisparador,
  };

  return (
    <div ref={raiz} className="relative inline-flex">
      {variante === "icono" ? (
        <BotonIcono
          {...propsDisparador}
          etiqueta={etiqueta}
          texto={String(children)}
          soloIcono
          variante="secundario"
          icono={ocupado ? <Spinner heredar className="h-4 w-4" /> : <IconoPuntos />}
        />
      ) : (
        <button
          {...propsDisparador}
          type="button"
          aria-label={etiqueta}
          className={`${BOTON[variante]} aria-disabled:cursor-not-allowed aria-disabled:opacity-60`}
        >
          {ocupado ? (
            <Spinner heredar className="h-4 w-4" />
          ) : (
            variante === "boton" && <IconoPuntos />
          )}
          {children}
        </button>
      )}
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
            <div role="presentation" className="flex flex-col border-b border-borde px-4 py-2">
              <p className="truncate text-sm font-semibold text-texto">{titulo}</p>
              {subtitulo && <p className="truncate text-sm text-texto-suave">{subtitulo}</p>}
            </div>
          )}
          {items.map((item) => {
            const clases = `${ITEM} ${item.peligro ? "text-error" : "text-texto"}`;
            return (
              <Fragment key={item.texto}>
                {item.separado && <div role="separator" className="my-1 border-t border-borde" />}
                {item.to ? (
                  <Link
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
                    type="button"
                    role="menuitem"
                    tabIndex={-1}
                    className={clases}
                    onClick={() => elegir(item)}
                  >
                    {item.texto}
                  </button>
                )}
              </Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
}
