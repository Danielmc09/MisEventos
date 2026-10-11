/** Devuelve `next` si es una ruta interna (empieza con `/`, no con `//` ni `/\`); si no, `/`. */
export function rutaSegura(next: string | null | undefined): string {
  return next && /^\/(?![/\\])/.test(next) ? next : "/";
}
