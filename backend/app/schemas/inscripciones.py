from uuid import UUID

from pydantic import BaseModel, ConfigDict

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
