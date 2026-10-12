import { useId, type InputHTMLAttributes } from "react";
import { ALTURA_LINEA, bordeCampo, CAMPO, ETIQUETA_CAMPO, MENSAJE_ERROR } from "./estilosCampo";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export function Input({ label, error, id, className = "", ...props }: InputProps) {
  const generado = useId();
  const inputId = id ?? generado;
  const errorId = `${inputId}-error`;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={inputId} className={ETIQUETA_CAMPO}>
        {label}
      </label>
      <input
        {...props}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={
          [props["aria-describedby"], error && errorId].filter(Boolean).join(" ") || undefined
        }
        className={`${CAMPO} ${ALTURA_LINEA} ${bordeCampo(!!error)} ${className}`}
      />
      {error && (
        <p id={errorId} className={MENSAJE_ERROR}>
          {error}
        </p>
      )}
    </div>
  );
}
