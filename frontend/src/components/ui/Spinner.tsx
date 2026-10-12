export interface SpinnerProps {
  className?: string;
  /** Toma el color del texto que lo rodea (dentro de un botón). */
  heredar?: boolean;
}

export function Spinner({ className = "h-5 w-5", heredar = false }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label="Cargando"
      className={`inline-block rounded-full border-2 border-current border-t-transparent motion-safe:animate-spin ${
        heredar ? "" : "text-primario"
      } ${className}`}
    />
  );
}
