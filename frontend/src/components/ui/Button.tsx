import type { ButtonHTMLAttributes } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
}

export function Button({ loading, children, ...props }: ButtonProps) {
  void loading;
  return <button {...props}>{children}</button>;
}
