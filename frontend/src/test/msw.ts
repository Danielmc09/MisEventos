import { HttpResponse, type JsonBodyType } from "msw";
import type { paths } from "../api/schema";

type Contenido<
  P extends keyof paths,
  M extends keyof paths[P],
  S extends number,
> = paths[P][M] extends {
  responses: infer R;
}
  ? S extends keyof R
    ? R[S] extends { content: infer C }
      ? C[keyof C]
      : never
    : never
  : never;

/** Respuesta de un mock cuyo cuerpo tiene que coincidir con el que declara el OpenAPI para esa ruta, método y código. */
export function responder<P extends keyof paths, M extends keyof paths[P], S extends number>(
  _ruta: P,
  _metodo: M,
  status: S,
  cuerpo: Contenido<P, M, S>,
) {
  const headers = status >= 400 ? { "Content-Type": "application/problem+json" } : undefined;
  return HttpResponse.json(cuerpo as JsonBodyType, { status, headers });
}
