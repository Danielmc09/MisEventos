from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, ConfigDict, Field


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
