import type { ComponentProps, ReactNode } from "react";

export interface EnlaceProps {
  to: string;
  children: ReactNode;
}

export function Enlace(props: EnlaceProps) {
  void props;
  return null;
}

export function BotonEnlace(props: ComponentProps<"button">) {
  void props;
  return null;
}
