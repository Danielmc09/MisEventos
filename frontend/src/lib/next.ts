/** Devuelve `next` si es una ruta interna (empieza con `/`, no con `//` ni `/\`); si no, `/`. */
export function rutaSegura(next: string | null | undefined): string {
  return next && /^\/(?![/\\])/.test(next) ? next : "/";
}

/** `?next=<ruta>` para encadenar login y registro sin perder el destino; vacío si no hay `next` o no es una ruta interna. */
export function conservarNext(next: string | null): string {
  return next && rutaSegura(next) === next ? `?next=${encodeURIComponent(next)}` : "";
}
