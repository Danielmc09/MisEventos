/** Lo que comparten un botón y un enlace con aspecto de botón. */
export const BASE_BOTON =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-md py-2 font-semibold focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-acento disabled:cursor-not-allowed disabled:opacity-60 md:min-h-10 motion-safe:transition-[background-color,transform] motion-safe:duration-100 enabled:motion-safe:active:scale-97";

export const VARIANTES_BOTON = {
  primario: "bg-primario text-panel hover:bg-primario-hover",
  peligro: "bg-error text-panel hover:brightness-90",
  secundario: "bg-acento-suave text-tinta hover:brightness-95",
} as const;

export type VarianteBoton = keyof typeof VARIANTES_BOTON;
