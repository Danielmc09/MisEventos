export interface FieldError {
  field: string;
  message: string;
}

export interface ApiErrorInit {
  status: number;
  type: string;
  title: string;
  detail?: string;
  errors?: FieldError[];
  traceId?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly type: string;
  readonly title: string;
  readonly detail?: string;
  readonly errors: FieldError[];
  readonly traceId?: string;

  constructor({ status, type, title, detail, errors = [], traceId }: ApiErrorInit) {
    super(title);
    this.name = "ApiError";
    this.status = status;
    this.type = type;
    this.title = title;
    this.detail = detail;
    this.errors = errors;
    this.traceId = traceId;
  }
}
