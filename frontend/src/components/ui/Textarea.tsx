import { useId, type TextareaHTMLAttributes } from "react";
import { bordeCampo, CAMPO, ETIQUETA_CAMPO, MENSAJE_ERROR } from "./estilosCampo";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
}

export function Textarea({ label, error, id, className = "", ...props }: TextareaProps) {
  const generado = useId();
  const campoId = id ?? generado;
  const errorId = `${campoId}-error`;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={campoId} className={ETIQUETA_CAMPO}>
        {label}
      </label>
      <textarea
        {...props}
        id={campoId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className={`${CAMPO} ${bordeCampo(!!error)} ${className}`}
      />
      {error && (
        <p id={errorId} className={MENSAJE_ERROR}>
          {error}
        </p>
      )}
    </div>
  );
}
