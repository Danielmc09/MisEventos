"""Eventos: quién los crea y con qué reglas. Lanza excepciones de dominio; no sabe de HTTP."""

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.core.excepciones import DatosInvalidos, Forbidden
from app.core.permisos import Permiso, tiene_permiso
from app.models.evento import Event
from app.models.usuario import User
from app.schemas.eventos import EventoEntrada


class Eventos(Protocol):
    def por_id(self, id_evento: UUID) -> Event | None: ...
    def crear(self, evento: Event) -> Event: ...


def puede_ver(usuario: User | None, evento: Event) -> bool:
    return True


def crear(repo: Eventos, usuario: User, datos: EventoEntrada) -> Event:
    """Un borrador a nombre de quien lo crea."""
    if not tiene_permiso(usuario, Permiso.EVENTO_CREAR):
        raise Forbidden()
    if datos.start_at <= datetime.now(UTC):
        raise DatosInvalidos("start_at", "Tiene que estar en el futuro")
    return repo.crear(Event(**datos.model_dump(), organizer_id=usuario.id))
