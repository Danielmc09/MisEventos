"""Eventos: quién los crea, quién los ve y con qué reglas.

Lanza excepciones de dominio; no sabe nada de HTTP."""

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.core.excepciones import (
    Conflict,
    DatosInvalidos,
    Forbidden,
    NotFound,
    TransicionInvalida,
)
from app.core.permisos import Permiso, tiene_permiso
from app.models.evento import EstadoEvento, Event
from app.models.usuario import User
from app.schemas.eventos import EventoEdicion, EventoEntrada


class Eventos(Protocol):
    def por_id(self, id_evento: UUID) -> Event | None: ...
    def crear(self, evento: Event) -> Event: ...
    def por_id_para_escribir(self, id_evento: UUID) -> Event | None: ...
    def guardar(self, evento: Event) -> Event: ...
    def eliminar(self, evento: Event) -> None: ...


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


def _ya_empezo(evento: Event) -> bool:
    return evento.start_at <= datetime.now(UTC)


def _finalizado(evento: Event) -> bool:
    return evento.end_at < datetime.now(UTC)


def _para_escribir(repo: Eventos, usuario: User, id_evento: UUID) -> Event:
    """El evento bloqueado para modificarlo."""
    evento = repo.por_id_para_escribir(id_evento)
    if evento is None or not puede_ver(usuario, evento):
        raise NotFound()
    return evento


def _cambiar_estado(
    repo: Eventos, evento: Event, desde: set[EstadoEvento], hacia: EstadoEvento
) -> Event:
    if evento.status not in desde:
        raise TransicionInvalida()
    evento.status = hacia
    return repo.guardar(evento)


def publicar(repo: Eventos, usuario: User, id_evento: UUID) -> Event:
    evento = _para_escribir(repo, usuario, id_evento)
    if _ya_empezo(evento):
        raise TransicionInvalida("No se publica un evento que ya empezó")
    return _cambiar_estado(repo, evento, {EstadoEvento.DRAFT}, EstadoEvento.PUBLISHED)


def despublicar(repo: Eventos, usuario: User, id_evento: UUID) -> Event:
    evento = _para_escribir(repo, usuario, id_evento)
    return _cambiar_estado(repo, evento, {EstadoEvento.PUBLISHED}, EstadoEvento.DRAFT)


def cancelar(repo: Eventos, usuario: User, id_evento: UUID) -> Event:
    evento = _para_escribir(repo, usuario, id_evento)
    if _finalizado(evento):
        raise TransicionInvalida("No se cancela un evento que ya terminó")
    desde = {EstadoEvento.DRAFT, EstadoEvento.PUBLISHED}
    return _cambiar_estado(repo, evento, desde, EstadoEvento.CANCELLED)


def editar(repo: Eventos, usuario: User, id_evento: UUID, datos: EventoEdicion) -> Event:
    evento = _para_escribir(repo, usuario, id_evento)
    if evento.status == EstadoEvento.CANCELLED or _finalizado(evento):
        raise Conflict(titulo="Un evento cancelado o finalizado no se edita")
    cambios = datos.model_dump(exclude_unset=True)
    if "start_at" in cambios and cambios["start_at"] <= datetime.now(UTC):
        raise DatosInvalidos("start_at", "Tiene que estar en el futuro")
    if cambios.get("end_at", evento.end_at) <= cambios.get("start_at", evento.start_at):
        raise DatosInvalidos("end_at", "Tiene que ser posterior al inicio")
    for campo, valor in cambios.items():
        setattr(evento, campo, valor)
    return repo.guardar(evento)


def eliminar(repo: Eventos, usuario: User, id_evento: UUID) -> None:
    repo.eliminar(_para_escribir(repo, usuario, id_evento))
