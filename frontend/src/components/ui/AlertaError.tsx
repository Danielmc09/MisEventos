export interface AlertaErrorProps {
  title: string;
  detail?: string;
}

export function AlertaError({ title, detail }: AlertaErrorProps) {
  return (
    <p role="alert" className="break-words text-error">
      <strong>{title}</strong>
      {detail && <span className="block">{detail}</span>}
    </p>
  );
}
