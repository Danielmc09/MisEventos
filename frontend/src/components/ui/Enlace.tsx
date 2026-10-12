import type { ComponentProps, ReactNode } from "react";
import { Link } from "react-router-dom";

const BASE =
  "inline-flex min-h-11 max-w-full min-w-0 items-center focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-foco md:min-h-10";

const ESTILOS = {
  texto: `${BASE} text-primario underline underline-offset-4 break-words hover:decoration-2`,
  navegacion: `${BASE} font-medium text-primario hover:underline hover:underline-offset-4`,
  /** El título de una tarjeta: su área cubre toda la tarjeta (que tiene que ser `relative`). */
  tarjeta:
    "inline-flex min-h-11 max-w-full min-w-0 items-center font-bold break-words text-tinta after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:after:outline-3 focus-visible:after:outline-offset-2 focus-visible:after:outline-foco md:min-h-10",
  marca: `${BASE} text-lg font-bold text-tinta hover:underline hover:underline-offset-4`,
} as const;

export interface EnlaceProps extends Omit<ComponentProps<typeof Link>, "className"> {
  to: string;
  /** `navegacion`: sin subrayado hasta pasar el mouse (el encabezado). `marca`: el nombre de la app. */
  variante?: keyof typeof ESTILOS;
  children: ReactNode;
}

/** Navega a otra pantalla. Lo que no entra se corta con «…»: quien lo use pasa `title` para leerlo completo. */
export function Enlace({ variante = "texto", children, ...props }: EnlaceProps) {
  return (
    <Link {...props} className={ESTILOS[variante]}>
      {variante === "texto" || variante === "tarjeta" ? (
        children
      ) : (
        <span className="truncate">{children}</span>
      )}
    </Link>
  );
}

/** Una acción (no una navegación) con el aspecto de un enlace del encabezado. */
export function BotonEnlace({ children, ...props }: Omit<ComponentProps<"button">, "className">) {
  return (
    <button type="button" {...props} className={ESTILOS.navegacion}>
      {children}
    </button>
  );
}
