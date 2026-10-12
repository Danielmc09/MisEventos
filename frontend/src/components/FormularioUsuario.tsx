import { useId, useState, type FormEvent } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { components } from "../api/schema";
import { useSession } from "../stores/session";
import { AlertaError } from "./ui/AlertaError";
import { useAvisos } from "./ui/Avisos";
import { Button } from "./ui/Button";
import { DialogoConfirmacion } from "./ui/DialogoConfirmacion";
import { Formulario } from "./ui/Formulario";
import { Input } from "./ui/Input";
import { Modal } from "./ui/Modal";
import { Select } from "./ui/Select";
import { TextoSecundario } from "./ui/TextoSecundario";

export type UsuarioAdmin = components["schemas"]["UsuarioAdmin"];
type Rol = UsuarioAdmin["role"];
type Edicion = components["schemas"]["UsuarioEdicion"];

export const ROLES: Record<Rol, string> = {
  ATTENDEE: "Asistente",
  ORGANIZER: "Organizador",
  ADMIN: "Administrador",
};

export const nombreDe = (u: UsuarioAdmin) => u.full_name || u.email;

export interface FormularioUsuarioProps {
  usuario: UsuarioAdmin;
  /** Es la cuenta de quien está editando: no puede cambiar su propio rol ni su estado. */
  propio: boolean;
  onGuardado: () => void;
  onCancelar: () => void;
}

export function FormularioUsuario({
  usuario,
  propio,
  onGuardado,
  onCancelar,
}: FormularioUsuarioProps) {
  const avisar = useAvisos();
  const ayudaId = useId();
  const [nombre, setNombre] = useState(usuario.full_name ?? "");
  const [email, setEmail] = useState(usuario.email);
  const [rol, setRol] = useState<Rol>(usuario.role);
  const [activo, setActivo] = useState(String(usuario.is_active));
  const [errorNombre, setErrorNombre] = useState<string>();
  const [errorEmail, setErrorEmail] = useState<string>();
  const [general, setGeneral] = useState<string>();
  const [enviando, setEnviando] = useState(false);
  const [pendiente, setPendiente] = useState<Edicion>();

  async function guardar(cuerpo: Edicion) {
    setEnviando(true);
    try {
      const actualizado = await api<UsuarioAdmin>(`/admin/users/${usuario.id}`, {
        method: "PATCH",
        body: JSON.stringify(cuerpo),
      });
      if (propio && cuerpo.full_name !== undefined)
        useSession.getState().actualizarNombre(actualizado.full_name);
      avisar({ message: `Guardaste los cambios de ${nombreDe(actualizado)}`, tone: "exito" });
      onGuardado();
    } catch (err) {
      setPendiente(undefined);
      setEnviando(false);
      if (err instanceof ApiError && err.type === "email-taken") setErrorEmail(err.title);
      else setGeneral(err instanceof ApiError ? err.title : "Ocurrió un error inesperado");
    }
  }

  function enviar(e: FormEvent) {
    e.preventDefault();
    setGeneral(undefined);
    const nombreLimpio = nombre.trim();
    const emailLimpio = email.trim();
    // Un nombre que existía no se puede borrar; si ya estaba vacío, sigue vacío y no se manda.
    const faltaNombre = !nombreLimpio && usuario.full_name ? "Escribí el nombre" : undefined;
    const faltaEmail = !emailLimpio ? "Escribí el correo" : undefined;
    setErrorNombre(faltaNombre);
    setErrorEmail(faltaEmail);
    if (faltaNombre || faltaEmail) return;

    const cuerpo: Edicion = {};
    if (nombreLimpio !== (usuario.full_name ?? "")) cuerpo.full_name = nombreLimpio;
    if (emailLimpio !== usuario.email) cuerpo.email = emailLimpio;
    if (!propio && rol !== usuario.role) cuerpo.role = rol;
    if (!propio && (activo === "true") !== usuario.is_active) cuerpo.is_active = activo === "true";

    if (Object.keys(cuerpo).length === 0) onCancelar();
    else if (cuerpo.role !== undefined || cuerpo.is_active !== undefined) setPendiente(cuerpo);
    else void guardar(cuerpo);
  }

  const bloqueado = propio ? { disabled: true, "aria-describedby": ayudaId } : {};

  return (
    <>
      <Modal titulo={`Editar a ${nombreDe(usuario)}`} onCerrar={onCancelar}>
        <Formulario onSubmit={enviar} noValidate>
          <Input
            label="Nombre"
            value={nombre}
            error={errorNombre}
            onChange={(e) => setNombre(e.target.value)}
          />
          <Input
            label="Correo"
            type="email"
            value={email}
            error={errorEmail}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Select
            label="Rol"
            value={rol}
            onChange={(e) => setRol(e.target.value as Rol)}
            {...bloqueado}
          >
            {(Object.keys(ROLES) as Rol[]).map((r) => (
              <option key={r} value={r}>
                {ROLES[r]}
              </option>
            ))}
          </Select>
          <Select
            label="Estado"
            value={activo}
            onChange={(e) => setActivo(e.target.value)}
            {...bloqueado}
          >
            <option value="true">Activo</option>
            <option value="false">Inactivo</option>
          </Select>
          {propio && (
            <TextoSecundario id={ayudaId} pequeno>
              No podés cambiar tu propio rol ni tu estado
            </TextoSecundario>
          )}
          {general && <AlertaError title={general} />}
          <div className="flex flex-wrap justify-end gap-3">
            <Button type="button" variante="secundario" onClick={onCancelar}>
              Cancelar
            </Button>
            <Button type="submit" loading={enviando && !pendiente}>
              Guardar
            </Button>
          </div>
        </Formulario>
      </Modal>
      {pendiente && (
        <DialogoConfirmacion
          titulo={
            pendiente.is_active === undefined
              ? `¿Cambiar el rol de ${nombreDe(usuario)}?`
              : `¿${pendiente.is_active ? "Reactivar" : "Desactivar"} a ${nombreDe(usuario)}?`
          }
          mensaje={
            pendiente.is_active === undefined
              ? `Va a pasar a ser ${ROLES[rol].toLowerCase()}. Tiene efecto en su siguiente acción.`
              : pendiente.is_active
                ? "Va a poder volver a entrar con su cuenta."
                : "No va a poder iniciar sesión."
          }
          confirmar={
            pendiente.is_active === undefined
              ? "Cambiar rol"
              : pendiente.is_active
                ? "Reactivar"
                : "Sí, desactivar"
          }
          variante={pendiente.is_active === false ? "peligro" : "primario"}
          cargando={enviando}
          onConfirmar={() => void guardar(pendiente)}
          onVolver={() => setPendiente(undefined)}
        />
      )}
    </>
  );
}
