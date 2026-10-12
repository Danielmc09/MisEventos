import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";
import {
  FormularioUsuario,
  ROLES,
  nombreDe,
  type UsuarioAdmin,
} from "../../components/FormularioUsuario";
import { AlertaError } from "../../components/ui/AlertaError";
import { BotonIcono } from "../../components/ui/BotonIcono";
import { Chip } from "../../components/ui/Chip";
import { EstadoVacio } from "../../components/ui/EstadoVacio";
import { IconoLapiz } from "../../components/ui/iconos/IconoLapiz";
import { Input } from "../../components/ui/Input";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";
import { Paginacion } from "../../components/ui/Paginacion";
import { Pestanas } from "../../components/ui/Pestanas";
import { Select } from "../../components/ui/Select";
import { Spinner } from "../../components/ui/Spinner";
import { Tabla } from "../../components/ui/Tabla";
import { Tarjeta } from "../../components/ui/Tarjeta";
import { useSesionVigente, useSession, useTienePermiso } from "../../stores/session";

type Rol = UsuarioAdmin["role"];

/** Cada pestaña es un preset del filtro de rol. */
const GRUPOS = [
  { id: "todos", titulo: "Todos", roles: [] as Rol[] },
  { id: "equipo", titulo: "Equipo", roles: ["ADMIN", "ORGANIZER"] as Rol[] },
  { id: "asistentes", titulo: "Asistentes", roles: ["ATTENDEE"] as Rol[] },
];

function useDemorado(valor: string, ms: number) {
  const [demorado, setDemorado] = useState(valor);
  useEffect(() => {
    const t = setTimeout(() => setDemorado(valor), ms);
    return () => clearTimeout(t);
  }, [valor, ms]);
  return demorado;
}

export default function AdminUsuarios() {
  const vigente = useSesionVigente();
  const puede = useTienePermiso("usuarios:gestionar");
  const propioId = useSession((s) => s.user?.id);

  const [busqueda, setBusqueda] = useState("");
  const q = useDemorado(busqueda, 300);
  const [grupo, setGrupo] = useState("todos");
  const [rol, setRol] = useState("");
  const [estado, setEstado] = useState("");
  const [numero, setNumero] = useState(1);
  const [version, setVersion] = useState(0);
  const [datos, setDatos] = useState<components["schemas"]["Pagina_UsuarioAdmin_"]>();
  const [error, setError] = useState<string>();
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
                    const nombre = nombreDe(u);
                    return {
                      id: u.id,
                      celdas: [
                        u.full_name ?? "—",
                        u.email,
                        ROLES[u.role],
                        <Chip key="estado" tono={u.is_active ? "exito" : "neutro"}>
                          {u.is_active ? "Activo" : "Inactivo"}
                        </Chip>,
                        u.active_registrations,
                        <BotonIcono
                          key="acciones"
                          etiqueta={`Editar a ${nombre}`}
                          texto="Editar"
                          icono={<IconoLapiz />}
                          onClick={() => setEditando(u)}
                        />,
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
      {editando && (
        <FormularioUsuario
          usuario={editando}
          propio={editando.id === propioId}
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
