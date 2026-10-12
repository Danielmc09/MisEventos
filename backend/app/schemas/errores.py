from pydantic import BaseModel, ConfigDict


class ErrorDeCampo(BaseModel):
    field: str
    message: str


class Problema(BaseModel):
    """Cuerpo de error según RFC 9457 (application/problem+json). Acepta miembros de extensión:
    un error de dominio puede sumar los suyos (por ejemplo, `conflicts`)."""

    model_config = ConfigDict(extra="allow")

    type: str
    title: str
    status: int
    detail: str | None = None
    trace_id: str
    errors: list[ErrorDeCampo] | None = None
