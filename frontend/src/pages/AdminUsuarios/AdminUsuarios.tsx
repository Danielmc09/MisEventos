import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";
import { AlertaError } from "../../components/ui/AlertaError";
import { useAvisos } from "../../components/ui/Avisos";
import { Button } from "../../components/ui/Button";
import { Chip } from "../../components/ui/Chip";
import { DialogoConfirmacion } from "../../components/ui/DialogoConfirmacion";
import { EstadoVacio } from "../../components/ui/EstadoVacio";
import { Formulario } from "../../components/ui/Formulario";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";
import { Paginacion } from "../../components/ui/Paginacion";
import { Pestanas } from "../../components/ui/Pestanas";
import { Select } from "../../components/ui/Select";
import { Spinner } from "../../components/ui/Spinner";
import { Tabla } from "../../components/ui/Tabla";
import { Tarjeta } from "../../components/ui/Tarjeta";
import { useSesionVigente, useSession, useTienePermiso } from "../../stores/session";

type UsuarioAdmin = components["schemas"]["UsuarioAdmin"];
type Rol = UsuarioAdmin["role"];
type Edicion = components["schemas"]["UsuarioEdicion"];

const ROLES: Record<Rol, string> = {
  ATTENDEE: "Asistente",
  ORGANIZER: "Organizador",
  ADMIN: "Administrador",
};

/** Cada pestaña es un preset del filtro de rol. */
const GRUPOS = [
  { id: "todos", titulo: "Todos", roles: [] as Rol[] },
  { id: "equipo", titulo: "Equipo", roles: ["ADMIN", "ORGANIZER"] as Rol[] },
  { id: "asistentes", titulo: "Asistentes", roles: ["ATTENDEE"] as Rol[] },
];

type Pendiente =
  { tipo: "rol"; usuario: UsuarioAdmin; rol: Rol } | { tipo: "estado"; usuario: UsuarioAdmin };

const nombreDe = (u: UsuarioAdmin) => u.full_name || u.email;

function useDemorado(valor: string, ms: number) {
  const [demorado, setDemorado] = useState(valor);
  useEffect(() => {
    const t = setTimeout(() => setDemorado(valor), ms);
    return () => clearTimeout(t);
  }, [valor, ms]);
  return demorado;
}

function FormularioNombre({
  usuario,
  onGuardado,
  onCancelar,
}: {
  usuario: UsuarioAdmin;
  onGuardado: () => void;
  onCancelar: () => void;
}) {
  const avisar = useAvisos();
  const [nombre, setNombre] = useState(usuario.full_name ?? "");
  const [error, setError] = useState<string>();
  const [general, setGeneral] = useState<string>();
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!nombre.trim()) {
      setError("Escribí el nombre");
      return;
    }
    setError(undefined);
    setGeneral(undefined);
    setEnviando(true);
    try {
      const cuerpo: Edicion = { full_name: nombre.trim() };
      const actualizado = await api<UsuarioAdmin>(`/admin/users/${usuario.id}`, {
        method: "PATCH",
        body: JSON.stringify(cuerpo),
      });
      if (usuario.id === useSession.getState().user?.id)
        useSession.getState().actualizarNombre(actualizado.full_name);
      avisar({ message: "Guardaste el nombre", tone: "exito" });
      onGuardado();
    } catch (err) {
      setGeneral(err instanceof ApiError ? err.title : "Ocurrió un error inesperado");
      setEnviando(false);
    }
  }

  return (
    <Modal titulo="Editar nombre" onCerrar={onCancelar}>
      <Formulario onSubmit={enviar} noValidate>
        <Input
          label="Nombre"
          value={nombre}
          error={error}
          onChange={(e) => setNombre(e.target.value)}
        />
        {general && <AlertaError title={general} />}
        <div className="flex flex-wrap justify-end gap-3">
          <Button type="button" variante="secundario" onClick={onCancelar}>
            Cancelar
          </Button>
          <Button type="submit" loading={enviando}>
            Guardar
          </Button>
        </div>
      </Formulario>
    </Modal>
  );
}

export default function AdminUsuarios() {
  const vigente = useSesionVigente();
  const puede = useTienePermiso("usuarios:gestionar");
  const propioId = useSession((s) => s.user?.id);
  const avisar = useAvisos();

  const [busqueda, setBusqueda] = useState("");
  const q = useDemorado(busqueda, 300);
  const [grupo, setGrupo] = useState("todos");
  const [rol, setRol] = useState("");
  const [estado, setEstado] = useState("");
  const [numero, setNumero] = useState(1);
  const [version, setVersion] = useState(0);
  const [datos, setDatos] = useState<components["schemas"]["Pagina_UsuarioAdmin_"]>();
  const [error, setError] = useState<string>();
  const [pendiente, setPendiente] = useState<Pendiente>();
  const [confirmando, setConfirmando] = useState(false);
  const [editando, setEditando] = useState<UsuarioAdmin>();

  useEffect(() => {
    if (!vigente || !puede) return;
    const params = new URLSearchParams({ page: String(numero) });
    if (q) params.set("q", q);
    const roles = rol ? [rol] : (GRUPOS.find((g) => g.id === grupo)?.roles ?? []);
    roles.forEach((r) => params.append("role", r));
    if (estado) params.set("is_active", estado);
    let activo = true;
    api<components["schemas"]["Pagina_UsuarioAdmin_"]>(`/admin/users?${params}`).then(
      (d) => {
        if (!activo) return;
        setDatos(d);
        setError(undefined);
      },
      (e) => activo && setError(e instanceof ApiError ? e.title : "Ocurrió un error inesperado"),
    );
    return () => {
      activo = false;
    };
  }, [vigente, puede, q, grupo, rol, estado, numero, version]);

  if (!vigente) return <Navigate to="/login" replace />;
  if (!puede)
    return (
      <Pagina>
        <TituloPagina>No tenés permiso para ver esta página</TituloPagina>
      </Pagina>
    );

  async function confirmar() {
    if (!pendiente) return;
    const { usuario } = pendiente;
    const cuerpo: Edicion =
      pendiente.tipo === "rol" ? { role: pendiente.rol } : { is_active: !usuario.is_active };
    const exito =
      pendiente.tipo === "rol"
        ? `Cambiaste el rol de ${nombreDe(usuario)}`
        : `${usuario.is_active ? "Desactivaste a" : "Reactivaste a"} ${nombreDe(usuario)}`;
    setConfirmando(true);
    try {
      await api(`/admin/users/${usuario.id}`, { method: "PATCH", body: JSON.stringify(cuerpo) });
      avisar({ message: exito, tone: "exito" });
      setVersion((v) => v + 1);
    } catch (e) {
      avisar({
        message: e instanceof ApiError ? e.title : "Ocurrió un error inesperado",
        tone: "error",
      });
    } finally {
      setConfirmando(false);
      setPendiente(undefined);
    }
  }

  const filtrar = (cambiar: (v: string) => void) => (v: string) => {
    cambiar(v);
    setNumero(1);
  };

  const quitarFiltros = () => {
    setBusqueda("");
    setGrupo("todos");
    setRol("");
    setEstado("");
    setNumero(1);
  };

  const rolesDelGrupo = GRUPOS.find((g) => g.id === grupo)?.roles ?? [];

  return (
    <Pagina ancho="ancho">
      <TituloPagina>Usuarios</TituloPagina>
      <Tarjeta as="section" aria-label="Lista de usuarios">
        <Pestanas
          etiqueta="Grupo de usuarios"
          pestanas={GRUPOS}
          activa={grupo}
          onCambiar={(id) => {
            setGrupo(id);
            setRol("");
            setNumero(1);
          }}
        >
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <Input
                type="search"
                label="Buscar"
                placeholder="Nombre o correo"
                value={busqueda}
                onChange={(e) => {
                  setBusqueda(e.target.value);
                  setNumero(1);
                }}
              />
              {rolesDelGrupo.length !== 1 && (
                <Select label="Rol" value={rol} onChange={(e) => filtrar(setRol)(e.target.value)}>
                  <option value="">Todos</option>
                  {(rolesDelGrupo.length ? rolesDelGrupo : (Object.keys(ROLES) as Rol[])).map(
                    (r) => (
                      <option key={r} value={r}>
                        {ROLES[r]}
                      </option>
                    ),
                  )}
                </Select>
              )}
              <Select
                label="Estado"
                value={estado}
                onChange={(e) => filtrar(setEstado)(e.target.value)}
              >
                <option value="">Todos</option>
                <option value="true">Activos</option>
                <option value="false">Inactivos</option>
              </Select>
            </div>
            {error && <AlertaError title={error} />}
            {!datos && !error && (
              <div className="flex justify-center p-6">
                <Spinner />
              </div>
            )}
            {datos && datos.items.length === 0 && (
              <EstadoVacio
                mensaje="No hay usuarios que coincidan con la búsqueda"
                accion="Quitar filtros"
                onAccion={quitarFiltros}
              />
            )}
            {datos && datos.items.length > 0 && (
              <>
                <Tabla
                  descripcion="Lista de usuarios"
                  columnas={[
                    "Nombre",
                    "Correo",
                    "Rol",
                    "Estado",
                    "Inscripciones activas",
                    "Acciones",
                  ]}
                  filas={datos.items.map((u) => {
                    const propio = u.id === propioId;
                    const nombre = nombreDe(u);
                    return {
                      id: u.id,
                      celdas: [
                        u.full_name ?? "—",
                        u.email,
                        propio ? (
                          ROLES[u.role]
                        ) : (
                          <Select
                            key="rol"
                            aria-label={`Rol de ${nombre}`}
                            value={u.role}
                            onChange={(e) =>
                              setPendiente({ tipo: "rol", usuario: u, rol: e.target.value as Rol })
                            }
                          >
                            {(Object.keys(ROLES) as Rol[]).map((r) => (
                              <option key={r} value={r}>
                                {ROLES[r]}
                              </option>
                            ))}
                          </Select>
                        ),
                        <Chip key="estado" tono={u.is_active ? "exito" : "neutro"}>
                          {u.is_active ? "Activo" : "Inactivo"}
                        </Chip>,
                        u.active_registrations,
                        <div key="acciones" className="flex gap-2">
                          <Button
                            variante="secundario"
                            aria-label={`Editar nombre de ${nombre}`}
                            onClick={() => setEditando(u)}
                          >
                            Editar nombre
                          </Button>
                          {!propio && (
                            <Button
                              variante={u.is_active ? "peligro" : "secundario"}
                              aria-label={`${u.is_active ? "Desactivar" : "Reactivar"} a ${nombre}`}
                              onClick={() => setPendiente({ tipo: "estado", usuario: u })}
                            >
                              {u.is_active ? "Desactivar" : "Reactivar"}
                            </Button>
                          )}
                        </div>,
                      ],
                    };
                  })}
                />
                <Paginacion pagina={datos.page} paginas={datos.pages} onCambiar={setNumero} />
              </>
            )}
          </div>
        </Pestanas>
      </Tarjeta>
      {pendiente && (
        <DialogoConfirmacion
          titulo={
            pendiente.tipo === "rol"
              ? `¿Cambiar el rol de ${nombreDe(pendiente.usuario)}?`
              : `¿${pendiente.usuario.is_active ? "Desactivar" : "Reactivar"} a ${nombreDe(pendiente.usuario)}?`
          }
          mensaje={
            pendiente.tipo === "rol"
              ? `Va a pasar a ser ${ROLES[pendiente.rol].toLowerCase()}. Tiene efecto en su siguiente acción.`
              : pendiente.usuario.is_active
                ? "No va a poder iniciar sesión."
                : "Va a poder volver a entrar con su cuenta."
          }
          confirmar={
            pendiente.tipo === "rol"
              ? "Cambiar rol"
              : pendiente.usuario.is_active
                ? "Sí, desactivar"
                : "Reactivar"
          }
          cargando={confirmando}
          onConfirmar={confirmar}
          onVolver={() => setPendiente(undefined)}
        />
      )}
      {editando && (
        <FormularioNombre
          usuario={editando}
          onCancelar={() => setEditando(undefined)}
          onGuardado={() => {
            setEditando(undefined);
            setVersion((v) => v + 1);
          }}
        />
      )}
    </Pagina>
  );
}
