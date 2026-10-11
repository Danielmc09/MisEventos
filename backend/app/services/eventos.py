"""Eventos: quién los crea, quién los ve y con qué reglas.

Lanza excepciones de dominio; no sabe nada de HTTP."""

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.core.excepciones import DatosInvalidos, Forbidden, NotFound
from app.core.permisos import Permiso, tiene_permiso
from app.models.evento import EstadoEvento, Event
from app.models.usuario import User
from app.schemas.eventos import EventoEntrada


class Eventos(Protocol):
    def por_id(self, id_evento: UUID) -> Event | None: ...
    def crear(self, evento: Event) -> Event: ...


def puede_ver(usuario: User | None, evento: Event) -> bool:
    """Publicados y cancelados, todos. Un borrador, su dueño (si puede crear eventos) y el admin."""
    if evento.status != EstadoEvento.DRAFT:
        return True
    if usuario is None:
        return False
    if tiene_permiso(usuario, Permiso.EVENTO_GESTIONAR_TODOS):
        return True
    return tiene_permiso(usuario, Permiso.EVENTO_CREAR) and evento.organizer_id == usuario.id


def obtener(repo: Eventos, usuario: User | None, id_evento: UUID) -> Event:
    """El evento, o NotFound si no existe o si no lo puede ver: no se revela que existe."""
    evento = repo.por_id(id_evento)
    if evento is None or not puede_ver(usuario, evento):
        raise NotFound()
    return evento


def crear(repo: Eventos, usuario: User, datos: EventoEntrada) -> Event:
    """Un borrador a nombre de quien lo crea."""
    if not tiene_permiso(usuario, Permiso.EVENTO_CREAR):
        raise Forbidden()
    if datos.start_at <= datetime.now(UTC):
        raise DatosInvalidos("start_at", "Tiene que estar en el futuro")
    return repo.crear(Event(**datos.model_dump(), organizer_id=usuario.id))
