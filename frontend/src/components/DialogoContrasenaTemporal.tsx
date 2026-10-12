import { useAvisos } from "./ui/Avisos";
import { Button } from "./ui/Button";
import { Modal } from "./ui/Modal";
import { Monoespaciado } from "./ui/Monoespaciado";
import { TextoSecundario } from "./ui/TextoSecundario";

export interface DialogoContrasenaTemporalProps {
  /** A quién pertenece: su nombre, o su correo si no tiene. */
  nombre: string;
  contrasena: string;
  onCerrar: () => void;
}

/** Muestra una contraseña temporal. Solo existe mientras el diálogo está abierto: no pasa por ningún store. */
export function DialogoContrasenaTemporal({
  nombre,
  contrasena,
  onCerrar,
}: DialogoContrasenaTemporalProps) {
  const avisar = useAvisos();

  async function copiar() {
    await navigator.clipboard.writeText(contrasena);
    avisar({ message: "Copiada", tone: "exito" });
  }

  return (
    <Modal titulo={`Contraseña temporal de ${nombre}`} onCerrar={onCerrar}>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <Monoespaciado>{contrasena}</Monoespaciado>
          <TextoSecundario>No se va a volver a mostrar</TextoSecundario>
          <TextoSecundario>
            Pasásela a la persona: la va a tener que cambiar al entrar.
          </TextoSecundario>
        </div>
        <div className="flex flex-wrap justify-end gap-3">
          <Button type="button" variante="secundario" onClick={() => void copiar()}>
            Copiar
          </Button>
          <Button type="button" onClick={onCerrar}>
            Cerrar
          </Button>
        </div>
      </div>
    </Modal>
  );
}
