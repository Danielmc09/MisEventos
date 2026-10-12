import { useId, type SelectHTMLAttributes } from "react";
import { ALTURA_LINEA, bordeCampo, CAMPO, ETIQUETA_CAMPO, MENSAJE_ERROR } from "./estilosCampo";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  error?: string;
}

export function Select({ label, error, id, className = "", children, ...props }: SelectProps) {
  const generado = useId();
  const campoId = id ?? generado;
  const errorId = `${campoId}-error`;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={campoId} className={ETIQUETA_CAMPO}>
        {label}
      </label>
      <select
        {...props}
        id={campoId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className={`${CAMPO} ${ALTURA_LINEA} ${bordeCampo(!!error)} ${className}`}
      >
        {children}
      </select>
      {error && (
        <p id={errorId} className={MENSAJE_ERROR}>
          {error}
        </p>
      )}
    </div>
  );
}
