import type { ReactNode } from "react";
import type { ToastProps } from "./Toast";

export type Aviso = Pick<ToastProps, "message" | "tone">;

// Provisional: el contenedor de avisos todavía no existe.
export function ProveedorAvisos({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function useAvisos(): (aviso: Aviso) => void {
  return () => {};
}
