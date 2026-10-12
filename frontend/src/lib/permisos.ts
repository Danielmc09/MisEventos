import type { Usuario } from "../stores/session";

export type Permiso = "evento:crear";

/** El usuario que devuelve la API trae el rol, no los permisos: este mapa es el espejo del backend. */
const PERMISOS_POR_ROL: Record<Usuario["role"], readonly Permiso[]> = {
  ATTENDEE: [],
  ORGANIZER: ["evento:crear"],
  ADMIN: ["evento:crear"],
};

export function tienePermiso(user: Usuario | null, permiso: Permiso): boolean {
  return !!user && PERMISOS_POR_ROL[user.role].includes(permiso);
}
