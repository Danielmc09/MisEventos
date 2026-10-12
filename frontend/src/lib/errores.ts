import { ApiError } from "../api/errors";

export interface ErrorDeFormulario {
  /** Mensaje por nombre de campo (los 422 del backend). */
  campos: Record<string, string>;
  /** Mensaje general: el `title` del problem+json cuando el error no apunta a un campo. */
  general: string | null;
  /** Los mensajes de los campos que el formulario no muestra, para que se sepa qué corregir. */
  detalle?: string | null;
}

/**
 * `visibles` lista los campos que el formulario sabe mostrar. Un error de otro campo no se
 * pierde: pasa al mensaje general. Sin `visibles`, todos los campos se consideran visibles.
 */
export function errorDeFormulario(e: unknown, visibles?: readonly string[]): ErrorDeFormulario {
  if (!(e instanceof ApiError))
    return { campos: {}, general: "Ocurrió un error inesperado", detalle: null };
  const mostrables = e.errors.filter((x) => !visibles || visibles.includes(x.field));
  const ocultos = e.errors.filter((x) => !mostrables.includes(x));
  const campos = Object.fromEntries(mostrables.map((x) => [x.field, x.message]));
  return {
    campos,
    general: e.errors.length && !ocultos.length ? null : e.title,
    detalle: ocultos.length ? ocultos.map((x) => x.message).join(". ") : null,
  };
}
