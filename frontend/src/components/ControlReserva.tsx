import type { Sesion } from "../lib/useSesiones";
import { ChipCupos } from "./ChipCupos";
import { Button } from "./ui/Button";
import { Chip } from "./ui/Chip";
import { TextoSecundario } from "./ui/TextoSecundario";

interface Props {
  sesion: Pick<Sesion, "start_at" | "is_reserved" | "available_spots" | "reserved_count">;
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

  // La capacidad efectiva (la propia o la heredada del evento) es lo reservado más lo que queda.
  const chip = (
    <ChipCupos
      capacidad={sesion.reserved_count + sesion.available_spots}
      libres={sesion.available_spots}
      unidad="lugar"
    />
  );

  if (!inscrito) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <TextoSecundario>Inscribite al evento para reservar sesiones</TextoSecundario>
        {chip}
      </div>
    );
  }

  if (sesion.is_reserved) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <Chip tono="exito">Reservado</Chip>
        <Button variante="secundario" loading={trabajando} onClick={onCancelar}>
          Cancelar reserva
        </Button>
        {chip}
      </div>
    );
  }

  if (sesion.available_spots <= 0) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <Button disabled>Sin lugares</Button>
        {chip}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button loading={trabajando} onClick={onReservar}>
        Reservar lugar
      </Button>
      {chip}
    </div>
  );
}
