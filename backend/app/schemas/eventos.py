from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    computed_field,
    field_validator,
)

from app.models.evento import EstadoEvento
from app.schemas.comunes import EntradaBase, FechaUTC


class EventoEntrada(EntradaBase):
    # status y organizer_id (y cualquier otro campo) no se aceptan: los decide el servidor.
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=150)]
    description: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, max_length=200)
    start_at: FechaUTC
    end_at: FechaUTC
    capacity: int = Field(ge=1, le=100_000)

    @field_validator("end_at")
    @classmethod
    def fin_despues_del_inicio(cls, end_at: datetime, info: ValidationInfo) -> datetime:
        start_at = info.data.get("start_at")  # no está si start_at ya falló
        if start_at is not None and end_at <= start_at:
            raise ValueError("Tiene que ser posterior al inicio")
        return end_at


class EventoEdicion(EntradaBase):
    """Solo lo que cambia. Las fechas se comparan con lo guardado en el servicio."""

    model_config = ConfigDict(extra="forbid")

    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=150)]
        | None
    ) = None
    description: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, max_length=200)
    start_at: FechaUTC | None = None
    end_at: FechaUTC | None = None
    capacity: int | None = Field(default=None, ge=1, le=100_000)

    @field_validator("name", "start_at", "end_at", "capacity")
    @classmethod
    def no_nulo(cls, valor: object) -> object:
        # Ausente sí (no cambia); null no: estos campos son obligatorios en el evento.
        if valor is None:
            raise ValueError("No puede ser nulo")
        return valor


class EventoSalida(BaseModel):
    id: UUID
    name: str
    description: str | None
    location: str | None
    start_at: FechaUTC
    end_at: FechaUTC
    capacity: int
    status: EstadoEvento
    organizer_id: UUID
    created_at: FechaUTC
    updated_at: FechaUTC
    # Las inscripciones activas. Quien no las cuenta responde 0.
    registered_count: int = 0

    @computed_field
    @property
    def available_spots(self) -> int:
        return self.capacity - self.registered_count

    @computed_field
    @property
    def is_finished(self) -> bool:
        # "Finalizado" no se guarda: se calcula en cada respuesta.
        return self.end_at < datetime.now(UTC)


class Cuando(StrEnum):
    UPCOMING = "upcoming"  # los que no terminaron: end_at >= ahora
    PAST = "past"


class OrdenEventos(StrEnum):
    START_AT = "start_at"
    START_AT_DESC = "-start_at"
    NAME = "name"


@dataclass(frozen=True)
class FiltrosEventos:
    """Lo que se pide al listar. La visibilidad no va acá: la decide el servicio."""

    q: str | None = None
    estados: list[EstadoEvento] | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
    cuando: Cuando = Cuando.UPCOMING
    orden: OrdenEventos = OrdenEventos.START_AT
