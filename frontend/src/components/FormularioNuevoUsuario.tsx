import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { components } from "../api/schema";
import { errorDeFormulario } from "../lib/errores";
import { DialogoContrasenaTemporal } from "./DialogoContrasenaTemporal";
import { ROLES, nombreDe, type UsuarioAdmin } from "./FormularioUsuario";
import { AlertaError } from "./ui/AlertaError";
import { Button } from "./ui/Button";
import { Formulario } from "./ui/Formulario";
import { Input } from "./ui/Input";
import { Modal } from "./ui/Modal";
import { Select } from "./ui/Select";

type Rol = UsuarioAdmin["role"];
type UsuarioCreado = components["schemas"]["UsuarioCreado"];

const CAMPOS_VISIBLES = ["full_name", "email", "role"];

export interface FormularioNuevoUsuarioProps {
  /** El usuario ya existe: la lista tiene que actualizarse, aunque el diálogo siga abierto. */
  onCreado: () => void;
  onCerrar: () => void;
}

export function FormularioNuevoUsuario({ onCreado, onCerrar }: FormularioNuevoUsuarioProps) {
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [rol, setRol] = useState<Rol>("ATTENDEE");
  const [errorEmail, setErrorEmail] = useState<string>();
  const [errorNombre, setErrorNombre] = useState<string>();
  const [general, setGeneral] = useState<{ title: string; detail?: string }>();
  const [enviando, setEnviando] = useState(false);
  // La contraseña vive solo acá: al cerrar el diálogo este componente se desmonta y se pierde.
  const [creado, setCreado] = useState<UsuarioCreado>();

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setGeneral(undefined);
    setErrorNombre(undefined);
    const emailLimpio = email.trim();
    const nombreLimpio = nombre.trim();
    const faltaEmail = !emailLimpio ? "Escribí el correo" : undefined;
    setErrorEmail(faltaEmail);
    if (faltaEmail) return;

    setEnviando(true);
    try {
      const usuario = await api<UsuarioCreado>("/admin/users", {
        method: "POST",
        body: JSON.stringify({
          email: emailLimpio,
          ...(nombreLimpio && { full_name: nombreLimpio }),
          role: rol,
        }),
      });
      setCreado(usuario);
      onCreado();
    } catch (err) {
      setEnviando(false);
      if (err instanceof ApiError && err.type === "email-taken") return setErrorEmail(err.title);
      const { campos, general, detalle } = errorDeFormulario(err, CAMPOS_VISIBLES);
      setErrorEmail(campos.email);
      setErrorNombre(campos.full_name);
      setGeneral(general ? { title: general, detail: detalle ?? undefined } : undefined);
    }
  }

  if (creado)
    return (
      <DialogoContrasenaTemporal
        nombre={nombreDe(creado)}
        contrasena={creado.temporary_password}
        onCerrar={onCerrar}
      />
    );

  return (
    <Modal titulo="Nuevo usuario" onCerrar={onCerrar}>
      <Formulario onSubmit={enviar} noValidate>
        <Input
          label="Correo"
          type="email"
          value={email}
          error={errorEmail}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          label="Nombre"
          value={nombre}
          error={errorNombre}
          onChange={(e) => setNombre(e.target.value)}
        />
        <Select label="Rol" value={rol} onChange={(e) => setRol(e.target.value as Rol)}>
          {(Object.keys(ROLES) as Rol[]).map((r) => (
            <option key={r} value={r}>
              {ROLES[r]}
            </option>
          ))}
        </Select>
        {general && <AlertaError {...general} />}
        <div className="flex flex-wrap justify-end gap-3">
          <Button type="button" variante="secundario" onClick={onCerrar}>
            Cancelar
          </Button>
          <Button type="submit" loading={enviando}>
            Crear usuario
          </Button>
        </div>
      </Formulario>
    </Modal>
  );
}
