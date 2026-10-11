from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.ponente import Speaker
from app.schemas.auth import Email
from app.schemas.comunes import FechaUTC

NombrePonente = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
]


class PonenteEntrada(BaseModel):
    # created_by (y cualquier otro campo) no se acepta: lo decide el servidor.
    model_config = ConfigDict(extra="forbid")

    full_name: NombrePonente
    bio: str | None = Field(default=None, max_length=2000)
    email: Email | None = None


class PonenteEdicion(BaseModel):
    """Solo lo que cambia. `bio` y `email` aceptan null para borrarlos."""

    model_config = ConfigDict(extra="forbid")

    full_name: NombrePonente | None = None
    bio: str | None = Field(default=None, max_length=2000)
    email: Email | None = None

    @field_validator("full_name")
    @classmethod
    def no_nulo(cls, valor: str | None) -> str:
        if valor is None:
            raise ValueError("No puede ser nulo")
        return valor


class PonenteSalida(BaseModel):
    id: UUID
    full_name: str
    bio: str | None
    created_by: UUID
    created_at: FechaUTC
    updated_at: FechaUTC
    # Dato personal. Para quien no puede verlo, el campo no se asigna y la ruta, que responde
    # con response_model_exclude_unset, lo omite: no sale ni como null.
    email: str | None = None

    @classmethod
    def de(cls, ponente: Speaker, *, con_email: bool) -> Self:
        return cls(**ponente.model_dump(exclude=None if con_email else {"email"}))
