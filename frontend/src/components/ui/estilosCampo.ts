/** Lo que comparten los campos de formulario. */
export const ETIQUETA_CAMPO = "text-sm font-medium text-texto";

export const CAMPO =
  "min-h-11 rounded-md border bg-panel px-3 py-2 text-texto focus-visible:outline-3 focus-visible:outline-offset-1 focus-visible:outline-acento md:min-h-10";

export const bordeCampo = (conError: boolean) => (conError ? "border-error" : "border-borde");

export const MENSAJE_ERROR = "text-sm text-error";
