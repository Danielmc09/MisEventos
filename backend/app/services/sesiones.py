"""Sesiones de un evento: las ve quien ve el evento; las gestionan su dueño o el admin.

Lanza excepciones de dominio; no sabe nada de HTTP."""

from typing import Protocol
from uuid import UUID

from app.core.excepciones import DatosInvalidos, NotFound
from app.models.evento import Event
from app.models.ponente import Speaker
from app.models.sesion import Session as Sesion
from app.models.usuario import User
from app.schemas.sesiones import SesionEdicion, SesionEntrada
from app.services import eventos as servicio_eventos
from app.services.eventos import Eventos
from app.services.ponentes import Ponentes

SesionConPonentes = tuple[Sesion, list[Speaker]]


class Sesiones(Protocol):
    def por_id(self, id_sesion: UUID) -> Sesion | None: ...
    def por_id_para_escribir(self, id_sesion: UUID) -> Sesion | None: ...
    def ponentes_de(self, ids_sesion: list[UUID]) -> dict[UUID, list[Speaker]]: ...
    def sesiones_de_ponentes(
        self, ids_ponente: list[UUID]
    ) -> list[tuple[Speaker, Sesion, Event]]: ...
    def crear(self, sesion: Sesion, ids_ponente: list[UUID]) -> Sesion: ...
    def guardar(self, sesion: Sesion, ids_ponente: list[UUID] | None) -> Sesion: ...
    def eliminar(self, sesion: Sesion) -> None: ...


def listar(
    eventos: Eventos, sesiones: Sesiones, usuario: User | None, id_evento: UUID
) -> list[SesionConPonentes]:
    """Las sesiones por hora de inicio. Si no puede ver el evento, NotFound."""
    servicio_eventos.obtener(eventos, usuario, id_evento)
    propias = eventos.sesiones_de(id_evento)
    ponentes = sesiones.ponentes_de([s.id for s in propias])
    return [(s, ponentes[s.id]) for s in propias]


def _bloquear_ponentes(ponentes: Ponentes, ids: list[UUID]) -> list[Speaker]:
    """Los bloquea en orden de id, el mismo en toda transacción: dos no se esperan en círculo."""
    bloqueados = []
    for id_ in sorted(set(ids)):
        ponente = ponentes.por_id_para_escribir(id_)
        if ponente is None:
            raise DatosInvalidos("speaker_ids", f"No existe el ponente {id_}")
        bloqueados.append(ponente)
    return bloqueados


def _validar_capacidad(evento: Event, capacidad: int | None) -> None:
    if capacidad is not None and capacidad > evento.capacity:
        raise DatosInvalidos("capacity", f"No puede superar la del evento ({evento.capacity})")


def crear(
    eventos: Eventos,
    sesiones: Sesiones,
    ponentes: Ponentes,
    usuario: User,
    id_evento: UUID,
    datos: SesionEntrada,
) -> SesionConPonentes:
    # Primero el evento y después los ponentes: el orden de los bloqueos es siempre ese.
    evento = servicio_eventos.para_escribir(eventos, usuario, id_evento)
    _validar_capacidad(evento, datos.capacity)
    asignados = _bloquear_ponentes(ponentes, datos.speaker_ids)
    sesion = Sesion(**datos.model_dump(exclude={"speaker_ids"}), event_id=evento.id)
    creada = sesiones.crear(sesion, [p.id for p in asignados])
    return creada, sesiones.ponentes_de([creada.id])[creada.id]


def _para_escribir(
    eventos: Eventos, sesiones: Sesiones, usuario: User, id_sesion: UUID
) -> tuple[Event, Sesion]:
    """El evento y la sesión bloqueados, en ese orden. La visibilidad y el permiso son los del
    evento: una sesión de un borrador ajeno es 404."""
    sesion = sesiones.por_id(id_sesion)
    if sesion is None:
        raise NotFound()
    evento = servicio_eventos.para_escribir(eventos, usuario, sesion.event_id)
    sesion = sesiones.por_id_para_escribir(id_sesion)
    if sesion is None:  # la borraron mientras se esperaba el bloqueo del evento
        raise NotFound()
    return evento, sesion


def editar(
    eventos: Eventos,
    sesiones: Sesiones,
    ponentes: Ponentes,
    usuario: User,
    id_sesion: UUID,
    datos: SesionEdicion,
) -> SesionConPonentes:
    evento, sesion = _para_escribir(eventos, sesiones, usuario, id_sesion)
    cambios = datos.model_dump(exclude_unset=True)
    ids_nuevos = cambios.pop("speaker_ids", None)
    if cambios.get("end_at", sesion.end_at) <= cambios.get("start_at", sesion.start_at):
        raise DatosInvalidos("end_at", "Tiene que ser posterior al inicio")
    _validar_capacidad(evento, cambios.get("capacity", sesion.capacity))
    actuales = [p.id for p in sesiones.ponentes_de([sesion.id])[sesion.id]]
    _bloquear_ponentes(ponentes, actuales if ids_nuevos is None else ids_nuevos)
    for campo, valor in cambios.items():
        setattr(sesion, campo, valor)
    ids_a_guardar = None if ids_nuevos is None else sorted(set(ids_nuevos))
    guardada = sesiones.guardar(sesion, ids_a_guardar)
    return guardada, sesiones.ponentes_de([guardada.id])[guardada.id]


def eliminar(eventos: Eventos, sesiones: Sesiones, usuario: User, id_sesion: UUID) -> None:
    _, sesion = _para_escribir(eventos, sesiones, usuario, id_sesion)
    sesiones.eliminar(sesion)
