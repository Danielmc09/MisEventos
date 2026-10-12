import type { Sesion } from "../lib/useSesiones";
import { quedan } from "../lib/plural";
import { Button } from "./ui/Button";
import { Insignia } from "./ui/Insignia";
import { TextoSecundario } from "./ui/TextoSecundario";

interface Props {
  sesion: Pick<Sesion, "start_at" | "is_reserved" | "available_spots">;
  /** Hay una sesión iniciada y la persona está inscrita al evento. */
  inscrito: boolean;
  eventoPublicado: boolean;
  trabajando?: boolean;
  onReservar: () => void;
  onCancelar: () => void;
}

/** Lo que se puede hacer con una sesión, según la inscripción y su cupo. */
export function ControlReserva({
  sesion,
  inscrito,
  eventoPublicado,
  trabajando = false,
  onReservar,
  onCancelar,
}: Props) {
  if (!eventoPublicado || new Date(sesion.start_at) <= new Date()) return null;

  if (!inscrito) {
    return <TextoSecundario>Inscribite al evento para reservar sesiones</TextoSecundario>;
  }

  if (sesion.is_reserved) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <Insignia tono="exito">Reservado</Insignia>
        <Button variante="secundario" loading={trabajando} onClick={onCancelar}>
          Cancelar reserva
        </Button>
        <TextoSecundario>{quedan(sesion.available_spots, "lugar", "lugares")}</TextoSecundario>
      </div>
    );
  }

  if (sesion.available_spots <= 0) return <Button disabled>Sin lugares</Button>;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button loading={trabajando} onClick={onReservar}>
        Reservar lugar
      </Button>
      <TextoSecundario>{quedan(sesion.available_spots, "lugar", "lugares")}</TextoSecundario>
    </div>
  );
}
