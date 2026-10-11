from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, computed_field

from app.models.evento import EstadoEvento
from app.schemas.comunes import FechaUTC


class EventoEntrada(BaseModel):
    name: str
    description: str | None = None
    location: str | None = None
    start_at: datetime
    end_at: datetime
    capacity: int


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
