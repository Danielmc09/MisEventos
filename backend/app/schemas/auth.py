from typing import Annotated, Literal
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.core.permisos import Rol
from app.schemas.comunes import FechaUTC


def _email_valido(valor: str) -> str:
    try:
        # Sin consultar DNS: el formato alcanza. Incluye el largo máximo de 254 caracteres.
        return validate_email(valor.strip(), check_deliverability=False).normalized
    except EmailNotValidError as error:
        raise ValueError("Debe ser un correo electrónico válido") from error


Email = Annotated[str, AfterValidator(_email_valido)]


class RegistroEntrada(BaseModel):
    # El rol (y cualquier otro campo) no se acepta: el registro público siempre crea ATTENDEE.
    model_config = ConfigDict(extra="forbid")

    email: Email
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)


class Mensaje(BaseModel):
    message: str


class TokenAcceso(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - el tipo de OAuth2, no un secreto
    expires_in: int


class UsuarioSalida(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: Rol
    is_active: bool
    must_change_password: bool
    created_at: FechaUTC
