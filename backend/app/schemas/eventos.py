from datetime import UTC, datetime
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
from app.schemas.comunes import FechaUTC


class EventoEntrada(BaseModel):
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
    # Hasta que existan las inscripciones no hay inscritos que contar.
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
