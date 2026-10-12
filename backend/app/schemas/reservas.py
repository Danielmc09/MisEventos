from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.reserva import EstadoReserva
from app.schemas.comunes import EntradaBase, FechaUTC


class ReservaEntrada(EntradaBase):
    """Sin campos: quién reserva sale del token y qué sesión, de la ruta. Cualquier campo que
    llegue se rechaza; en particular `confirm_overlap`: un cruce dentro del evento no se confirma,
    se bloquea."""

    model_config = ConfigDict(extra="forbid")


class ReservaSalida(BaseModel):
    id: UUID
    session_id: UUID
    status: EstadoReserva
    created_at: FechaUTC
