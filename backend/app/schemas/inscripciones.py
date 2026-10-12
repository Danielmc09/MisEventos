from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.evento import EstadoEvento
from app.models.inscripcion import EstadoInscripcion
from app.schemas.comunes import EntradaBase, FechaUTC


class InscripcionEntrada(EntradaBase):
    """Sin campos: quién se inscribe sale del token y a qué evento, de la ruta. Cualquier campo
    que llegue se rechaza, como en el resto de la API."""

    model_config = ConfigDict(extra="forbid")


class InscripcionSalida(BaseModel):
    id: UUID
    event_id: UUID
    status: EstadoInscripcion
    created_at: FechaUTC


class ResumenEvento(BaseModel):
    """Lo que el perfil muestra del evento de cada inscripción."""

    id: UUID
    name: str
    start_at: FechaUTC
    location: str | None
    status: EstadoEvento
    end_at: FechaUTC = Field(exclude=True)  # solo para calcular is_finished

    @computed_field
    @property
    def is_finished(self) -> bool:
        return self.end_at < datetime.now(UTC)


class InscripcionMia(BaseModel):
    id: UUID
    event_id: UUID
    status: EstadoInscripcion
    created_at: FechaUTC
    cancelled_at: FechaUTC | None
    event: ResumenEvento
