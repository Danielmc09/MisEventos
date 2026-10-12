import { Button } from "./Button";
import { TextoSecundario } from "./TextoSecundario";

export function EstadoVacio({
  mensaje,
  accion,
  onAccion,
}: {
  mensaje: string;
  accion?: string;
  onAccion?: () => void;
}) {
  return (
    <div className="flex flex-col items-start gap-3">
      <TextoSecundario>{mensaje}</TextoSecundario>
      {accion && onAccion && (
        <Button variante="secundario" onClick={onAccion}>
          {accion}
        </Button>
      )}
    </div>
  );
}
