/** Lo que comparten los campos de formulario. */
export const ETIQUETA_CAMPO = "text-sm font-medium text-texto";

export const CAMPO =
  "min-h-11 rounded-md border bg-panel px-3 py-2 text-texto focus-visible:outline-3 focus-visible:outline-offset-1 focus-visible:outline-foco md:min-h-10";

/** Alto fijo de los campos de una línea (44 px en móvil, 40 px en escritorio). */
export const ALTURA_LINEA = "h-11 md:h-10";

export const bordeCampo = (conError: boolean) => (conError ? "border-error" : "border-borde");

export const MENSAJE_ERROR = "text-sm text-error";
