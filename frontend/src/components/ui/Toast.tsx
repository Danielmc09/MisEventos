const TONOS = {
  exito: "bg-green-700",
  error: "bg-red-700",
  info: "bg-gray-800",
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
      className={`flex items-center gap-3 rounded-md px-4 py-3 text-white shadow-lg ${TONOS[tone]}`}
    >
      <span>{message}</span>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Cerrar aviso"
          className="ml-auto inline-flex min-h-11 min-w-11 items-center justify-center md:min-h-10 md:min-w-10"
        >
          ×
        </button>
      )}
    </div>
  );
}
