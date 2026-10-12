import type { ReactNode } from "react";

const TONOS = {
  exito: "bg-green-100 text-green-800",
  neutro: "bg-gray-100 text-gray-800",
} as const;

export interface InsigniaProps {
  tono?: keyof typeof TONOS;
  children: ReactNode;
}

export function Insignia({ tono = "neutro", children }: InsigniaProps) {
  return (
    <span className={`self-start rounded-full px-2 py-0.5 text-xs font-medium ${TONOS[tono]}`}>
      {children}
    </span>
  );
}
