from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
)

from app.schemas.comunes import EntradaBase, FechaUTC

Titulo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=150)]
# Una sala en blanco es lo mismo que no tener sala.
Sala = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=80),
    AfterValidator(lambda s: s or None),
]


class SesionEntrada(EntradaBase):
    # event_id (y cualquier otro campo) no se acepta: lo da la ruta.
    model_config = ConfigDict(extra="forbid")

    title: Titulo
    description: str | None = Field(default=None, max_length=2000)
    room: Sala | None = None
    start_at: FechaUTC
    end_at: FechaUTC
    # El tope es la capacidad del evento: lo revisa el servicio.
    capacity: int | None = Field(default=None, ge=1)
    speaker_ids: list[UUID] = Field(default_factory=list)

    @field_validator("end_at")
    @classmethod
    def fin_despues_del_inicio(cls, end_at: datetime, info: ValidationInfo) -> datetime:
        start_at = info.data.get("start_at")  # no está si start_at ya falló
        if start_at is not None and end_at <= start_at:
            raise ValueError("Tiene que ser posterior al inicio")
        return end_at


class SesionEdicion(EntradaBase):
    """Solo lo que cambia. Las fechas se comparan con lo guardado en el servicio; `speaker_ids`,
    si viene, reemplaza la lista entera."""

    model_config = ConfigDict(extra="forbid")

    title: Titulo | None = None
    description: str | None = Field(default=None, max_length=2000)
    room: Sala | None = None
    start_at: FechaUTC | None = None
    end_at: FechaUTC | None = None
    capacity: int | None = Field(default=None, ge=1)
    speaker_ids: list[UUID] | None = None

    @field_validator("title", "start_at", "end_at", "speaker_ids")
    @classmethod
    def no_nulo(cls, valor: object) -> object:
        # Ausente sí (no cambia); null no: son obligatorios en la sesión.
        if valor is None:
            raise ValueError("No puede ser nulo")
        return valor


class PonenteDeSesion(BaseModel):
    """Lo público de un ponente: sin el email."""

    id: UUID
    full_name: str
    bio: str | None


class SesionSalida(BaseModel):
    id: UUID
    event_id: UUID
    title: str
    description: str | None
    room: str | None
    start_at: FechaUTC
    end_at: FechaUTC
    capacity: int | None
    speakers: list[PonenteDeSesion]
    created_at: FechaUTC
    updated_at: FechaUTC
