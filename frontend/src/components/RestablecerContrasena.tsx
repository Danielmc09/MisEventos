import { useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { components } from "../api/schema";
import { DialogoContrasenaTemporal } from "./DialogoContrasenaTemporal";
import { nombreDe, type UsuarioAdmin } from "./FormularioUsuario";
import { useAvisos } from "./ui/Avisos";
import { DialogoConfirmacion } from "./ui/DialogoConfirmacion";

export interface RestablecerContrasenaProps {
  usuario: UsuarioAdmin;
  onTerminado: () => void;
}

/** Confirma, restablece y muestra la contraseña temporal. Esa contraseña vive solo en este componente. */
export function RestablecerContrasena({ usuario, onTerminado }: RestablecerContrasenaProps) {
  const avisar = useAvisos();
  const nombre = nombreDe(usuario);
  const [enviando, setEnviando] = useState(false);
  const [contrasena, setContrasena] = useState<string>();

  async function restablecer() {
    setEnviando(true);
    try {
      const { temporary_password } = await api<components["schemas"]["ContrasenaTemporal"]>(
        `/admin/users/${usuario.id}/reset-password`,
        { method: "POST" },
      );
      setContrasena(temporary_password);
    } catch (err) {
      avisar({
        message: err instanceof ApiError ? err.title : "Ocurrió un error inesperado",
        tone: "error",
      });
      onTerminado();
    }
  }

  if (contrasena)
    return (
      <DialogoContrasenaTemporal nombre={nombre} contrasena={contrasena} onCerrar={onTerminado} />
    );

  return (
    <DialogoConfirmacion
      titulo={`¿Restablecer la contraseña de ${nombre}?`}
      mensaje="Va a tener que elegir una nueva la próxima vez que entre."
      confirmar="Sí, restablecer"
      variante="primario"
      cargando={enviando}
      onConfirmar={() => void restablecer()}
      onVolver={onTerminado}
    />
  );
}
