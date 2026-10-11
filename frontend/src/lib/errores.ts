import { ApiError } from "../api/errors";

export interface ErrorDeFormulario {
  /** Mensaje por nombre de campo (los 422 del backend). */
  campos: Record<string, string>;
  /** Mensaje general: el `title` del problem+json cuando el error no apunta a un campo. */
  general: string | null;
}

export function errorDeFormulario(e: unknown): ErrorDeFormulario {
  if (!(e instanceof ApiError)) return { campos: {}, general: "Ocurrió un error inesperado" };
  const campos = Object.fromEntries(e.errors.map((x) => [x.field, x.message]));
  return { campos, general: e.errors.length ? null : e.title };
}
