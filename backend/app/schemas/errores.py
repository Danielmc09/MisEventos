from pydantic import BaseModel


class ErrorDeCampo(BaseModel):
    field: str
    message: str


class Problema(BaseModel):
    """Cuerpo de error según RFC 9457 (application/problem+json)."""

    type: str
    title: str
    status: int
    detail: str | None = None
    trace_id: str
    errors: list[ErrorDeCampo] | None = None
