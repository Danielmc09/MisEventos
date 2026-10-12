import type { ComponentProps } from "react";
import { Spinner } from "./Spinner";

export interface ButtonProps extends ComponentProps<"button"> {
  loading?: boolean;
  variante?: "primario" | "peligro" | "secundario";
}

const VARIANTES = {
  primario: "bg-indigo-600 text-white hover:bg-indigo-700 focus-visible:outline-indigo-600",
  peligro: "bg-red-700 text-white hover:bg-red-800 focus-visible:outline-red-700",
  secundario:
    "border border-gray-300 bg-white text-gray-900 hover:bg-gray-50 focus-visible:outline-indigo-600",
} as const;

export function Button({
  loading = false,
  variante = "primario",
  disabled,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 py-2 md:min-h-10 font-medium focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTES[variante]} ${className}`}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  );
}
