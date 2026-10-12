import { useSession } from "../stores/session";
import { ApiError } from "./errors";
import { irALogin } from "./navegacion";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function toApiError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => ({}));
  return new ApiError({
    status: response.status,
    type: body.type ?? "unknown-error",
    title: body.title ?? "Ocurrió un error inesperado",
    detail: body.detail,
    errors: body.errors,
    conflicts: body.conflicts,
    traceId: body.trace_id,
  });
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = useSession.getState().accessToken;
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError({
      status: 0,
      type: "network-error",
      title: "No se pudo conectar con el servidor",
    });
  }

  if (!response.ok) {
    // El token dura 60 minutos; al vencer, el 401 cierra la sesión.
    // Solo si el token que se mandó sigue siendo el vigente: si ya hay otra sesión, no se toca.
    if (response.status === 401 && useSession.getState().accessToken === token) {
      useSession.getState().cerrarSesion();
      irALogin();
    }
    throw await toApiError(response);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
