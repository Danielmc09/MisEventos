/** Gradientes armados solo con colores del tema; el texto blanco o `tinta` sobre cualquier tramo pasa 4.5:1. */
const GRADIENTES = [
  "bg-linear-to-br from-primario to-tinta",
  "bg-linear-to-br from-tinta to-acento",
  "bg-linear-to-br from-acento to-tinta",
  "bg-linear-to-br from-primario to-acento",
  "bg-linear-to-br from-tinta to-primario",
] as const;

/** Hash estable (djb2) del nombre: el mismo evento tiene siempre el mismo gradiente. */
const hash = (texto: string) => {
  let h = 5381;
  for (const c of texto) h = (h * 33 + c.codePointAt(0)!) >>> 0;
  return h;
};

export const claseGradiente = (nombre: string): string =>
  GRADIENTES[hash(nombre) % GRADIENTES.length];
