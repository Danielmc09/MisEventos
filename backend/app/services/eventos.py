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
from app.models.sesion import Session as Sesion
from app.models.usuario import User
from app.schemas.eventos import EventoEdicion, EventoEntrada, FiltrosEventos


class Eventos(Protocol):
    def por_id(self, id_evento: UUID) -> Event | None: ...
    def crear(self, evento: Event) -> Event: ...
    def por_id_para_escribir(self, id_evento: UUID) -> Event | None: ...
    def sesiones_de(self, id_evento: UUID) -> list[Sesion]: ...
    def inscritos(self, ids_evento: list[UUID]) -> dict[UUID, int]: ...
    def guardar(self, evento: Event) -> Event: ...
    def eliminar(self, evento: Event) -> None: ...
    def buscar(
        self,
        filtros: FiltrosEventos,
        *,
        ver_todo: bool,
        borradores_de: UUID | None,
        offset: int,
        limite: int,
    ) -> tuple[list[Event], int]: ...


def puede_ver(usuario: User | None, evento: Event) -> bool:
    """Publicados y cancelados, todos. Un borrador, su dueño (si puede crear eventos) y el admin."""
    if evento.status != EstadoEvento.DRAFT:
        return True
    if usuario is None:
        return False
    if tiene_permiso(usuario, Permiso.EVENTO_GESTIONAR_TODOS):
        return True
    return tiene_permiso(usuario, Permiso.EVENTO_CREAR) and evento.organizer_id == usuario.id


def listar(
    repo: Eventos, usuario: User | None, filtros: FiltrosEventos, offset: int, limite: int
) -> tuple[list[Event], int]:
    """Una página de lo que el usuario puede ver, con el total. Es la misma regla de `puede_ver`,
    pero la aplica la base: pedir `status=DRAFT` no muestra borradores que no le tocan."""
    ver_todo = usuario is not None and tiene_permiso(usuario, Permiso.EVENTO_GESTIONAR_TODOS)
    borradores_de = None
    if usuario is not None and not ver_todo and tiene_permiso(usuario, Permiso.EVENTO_CREAR):
        borradores_de = usuario.id
    return repo.buscar(
        filtros, ver_todo=ver_todo, borradores_de=borradores_de, offset=offset, limite=limite
    )


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


def ya_empezo(evento: Event) -> bool:
    return evento.start_at <= datetime.now(UTC)


def finalizado(evento: Event) -> bool:
    return evento.end_at < datetime.now(UTC)


def para_escribir(repo: Eventos, usuario: User, id_evento: UUID) -> Event:
    """El evento bloqueado para modificarlo. Primero la visibilidad (lo que no ve es 404, no se
    revela que existe) y después el permiso: el dueño que puede crear eventos, o el admin."""
    evento = repo.por_id_para_escribir(id_evento)
    if evento is None or not puede_ver(usuario, evento):
        raise NotFound()
    es_dueno = tiene_permiso(usuario, Permiso.EVENTO_CREAR) and evento.organizer_id == usuario.id
    if not (es_dueno or tiene_permiso(usuario, Permiso.EVENTO_GESTIONAR_TODOS)):
        raise Forbidden()
    return evento


def _cambiar_estado(
    repo: Eventos, evento: Event, desde: set[EstadoEvento], hacia: EstadoEvento
) -> Event:
    if evento.status not in desde:
        raise TransicionInvalida()
    evento.status = hacia
    return repo.guardar(evento)


def publicar(repo: Eventos, usuario: User, id_evento: UUID) -> Event:
    evento = para_escribir(repo, usuario, id_evento)
    if ya_empezo(evento):
        raise TransicionInvalida("No se publica un evento que ya empezó")
    return _cambiar_estado(repo, evento, {EstadoEvento.DRAFT}, EstadoEvento.PUBLISHED)


def despublicar(repo: Eventos, usuario: User, id_evento: UUID) -> Event:
    evento = para_escribir(repo, usuario, id_evento)
    return _cambiar_estado(repo, evento, {EstadoEvento.PUBLISHED}, EstadoEvento.DRAFT)


def cancelar(repo: Eventos, usuario: User, id_evento: UUID) -> Event:
    evento = para_escribir(repo, usuario, id_evento)
    if finalizado(evento):
        raise TransicionInvalida("No se cancela un evento que ya terminó")
    desde = {EstadoEvento.DRAFT, EstadoEvento.PUBLISHED}
    return _cambiar_estado(repo, evento, desde, EstadoEvento.CANCELLED)


def _exigir_sesiones_adentro(repo: Eventos, evento: Event, inicio: datetime, fin: datetime) -> None:
    """Las fechas nuevas no pueden dejar sesiones afuera. El evento ya está bloqueado, así que
    nadie agrega una sesión mientras tanto."""
    afuera = sum(1 for s in repo.sesiones_de(evento.id) if s.start_at < inicio or s.end_at > fin)
    if afuera:
        detalle = (
            "1 sesión queda fuera de las fechas nuevas"
            if afuera == 1
            else f"{afuera} sesiones quedan fuera de las fechas nuevas"
        )
        raise Conflict(
            detalle,
            tipo="sessions-outside-range",
            titulo="Las fechas nuevas dejan sesiones fuera del evento",
        )


def editar(repo: Eventos, usuario: User, id_evento: UUID, datos: EventoEdicion) -> Event:
    evento = para_escribir(repo, usuario, id_evento)
    if evento.status == EstadoEvento.CANCELLED or finalizado(evento):
        raise Conflict(titulo="Un evento cancelado o finalizado no se edita")
    cambios = datos.model_dump(exclude_unset=True)
    if "start_at" in cambios and cambios["start_at"] <= datetime.now(UTC):
        raise DatosInvalidos("start_at", "Tiene que estar en el futuro")
    if cambios.get("end_at", evento.end_at) <= cambios.get("start_at", evento.start_at):
        raise DatosInvalidos("end_at", "Tiene que ser posterior al inicio")
    if "start_at" in cambios or "end_at" in cambios:
        _exigir_sesiones_adentro(
            repo,
            evento,
            cambios.get("start_at", evento.start_at),
            cambios.get("end_at", evento.end_at),
        )
    for campo, valor in cambios.items():
        setattr(evento, campo, valor)
    return repo.guardar(evento)


def eliminar(repo: Eventos, usuario: User, id_evento: UUID) -> None:
    repo.eliminar(para_escribir(repo, usuario, id_evento))
