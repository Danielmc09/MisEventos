"""Eventos: quién puede crearlos. Lanza excepciones de dominio; no sabe nada de HTTP."""

from typing import Protocol
from uuid import UUID

from app.core.excepciones import Forbidden
from app.core.permisos import Permiso, tiene_permiso
from app.models.evento import Event
from app.models.usuario import User
from app.schemas.eventos import EventoEntrada


class Eventos(Protocol):
    def por_id(self, id_evento: UUID) -> Event | None: ...
    def crear(self, evento: Event) -> Event: ...


def crear(repo: Eventos, usuario: User, datos: EventoEntrada) -> Event:
    """Un borrador a nombre de quien lo crea."""
    if not tiene_permiso(usuario, Permiso.EVENTO_CREAR):
        raise Forbidden()
    return repo.crear(Event(**datos.model_dump(), organizer_id=usuario.id))
