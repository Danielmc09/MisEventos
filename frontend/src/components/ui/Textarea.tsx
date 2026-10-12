import { useId, type TextareaHTMLAttributes } from "react";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
}

export function Textarea({ label, error, id, className = "", ...props }: TextareaProps) {
  const generado = useId();
  const campoId = id ?? generado;
  const errorId = `${campoId}-error`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={campoId} className="text-sm font-medium text-gray-700">
        {label}
      </label>
      <textarea
        {...props}
        id={campoId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className={`rounded-md border px-3 py-2 ${error ? "border-red-600" : "border-gray-300"} ${className}`}
      />
      {error && (
        <p id={errorId} className="text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
