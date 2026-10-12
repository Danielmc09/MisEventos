import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export interface EnlaceBotonProps {
  to: string;
  children: ReactNode;
}

export function EnlaceBoton({ to, children }: EnlaceBotonProps) {
  return (
    <Link
      to={to}
      className="inline-flex min-h-11 items-center justify-center rounded-md bg-indigo-600 px-4 py-2 md:min-h-10 font-medium text-white hover:bg-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
    >
      {children}
    </Link>
  );
}
