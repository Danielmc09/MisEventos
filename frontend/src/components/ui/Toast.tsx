const TONOS = {
  exito: "bg-exito-suave text-exito",
  error: "bg-error-suave text-error",
  info: "bg-info-suave text-info",
} as const;

const ETIQUETAS = { exito: "Éxito", error: "Error", info: "Información" } as const;

const TRAZOS = {
  exito: "M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  error: "M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z",
  info: "m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z",
} as const;

export interface ToastProps {
  message: string;
  tone?: keyof typeof TONOS;
  onClose?: () => void;
}

export function Toast({ message, tone = "info", onClose }: ToastProps) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`pointer-events-auto flex items-center gap-3 rounded-lg py-3 pl-4 shadow-elevada motion-safe:animate-entrar ${
        onClose ? "pr-1" : "pr-4"
      } ${TONOS[tone]}`}
    >
      <svg
        role="img"
        aria-label={ETIQUETAS[tone]}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-6 w-6 shrink-0"
      >
        <path d={TRAZOS[tone]} />
      </svg>
      <span className="break-words">{message}</span>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Cerrar aviso"
          className="ml-auto inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-md text-xl focus-visible:outline-3 focus-visible:outline-acento md:min-h-10 md:min-w-10"
        >
          <span aria-hidden="true">×</span>
        </button>
      )}
    </div>
  );
}
