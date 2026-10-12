export interface FieldError {
  field: string;
  message: string;
}

/** La sesión con la que choca una reserva (miembro de extensión `conflicts` del problem+json). */
export interface SesionEnConflicto {
  session_id: string;
  title: string;
  start_at: string;
  end_at: string;
  room: string | null;
}

export interface ApiErrorInit {
  status: number;
  type: string;
  title: string;
  detail?: string;
  errors?: FieldError[];
  conflicts?: SesionEnConflicto[];
  traceId?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly type: string;
  readonly title: string;
  readonly detail?: string;
  readonly errors: FieldError[];
  readonly conflicts: SesionEnConflicto[];
  readonly traceId?: string;

  constructor({ status, type, title, detail, errors = [], conflicts = [], traceId }: ApiErrorInit) {
    super(title);
    this.name = "ApiError";
    this.status = status;
    this.type = type;
    this.title = title;
    this.detail = detail;
    this.errors = errors;
    this.conflicts = conflicts;
    this.traceId = traceId;
  }
}
