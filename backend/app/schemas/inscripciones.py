from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, computed_field

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


class SesionReservada(BaseModel):
    """Lo que el perfil muestra de cada sesión reservada."""

    id: UUID
    title: str
    start_at: FechaUTC
    end_at: FechaUTC
    room: str | None


class InscripcionMia(BaseModel):
    id: UUID
    event_id: UUID
    status: EstadoInscripcion
    created_at: FechaUTC
    cancelled_at: FechaUTC | None
    event: ResumenEvento
    reserved_sessions: list[SesionReservada] = Field(
        description="Las reservas activas en ese evento, por hora de inicio. Vacía si la "
        "inscripción está cancelada"
    )


class Inscrito(BaseModel):
    """Lo que el dueño del evento ve de cada inscrito."""

    full_name: str | None
    email: str
    status: EstadoInscripcion
    created_at: FechaUTC


# Se calcula con Decimal para no arrastrar errores de redondeo, y viaja como número en el JSON.
Porcentaje = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


class OcupacionSesionSalida(BaseModel):
    id: UUID
    title: str
    reserved: int
    capacity: int = Field(description="La capacidad de la sesión o, si no tiene, la del evento")
    occupancy_pct: Porcentaje


class EstadisticasSalida(BaseModel):
    active: int
    cancelled: int
    capacity: int
    available_spots: int
    occupancy_pct: Porcentaje
    sessions: list[OcupacionSesionSalida] = Field(description="Por hora de inicio")
