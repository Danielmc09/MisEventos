"""Sesiones de un evento: las ve quien ve el evento; las gestionan su dueño o el admin.

Lanza excepciones de dominio; no sabe nada de HTTP."""

from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from app.core.excepciones import Conflict, DatosInvalidos, NotFound
from app.core.horarios import se_cruzan
from app.models.evento import EstadoEvento, Event
from app.models.ponente import Speaker
from app.models.sesion import Session as Sesion
from app.models.usuario import User
from app.schemas.sesiones import SesionEdicion, SesionEntrada
from app.services import eventos as servicio_eventos
from app.services.eventos import Eventos
from app.services.ponentes import Ponentes

SesionConPonentes = tuple[Sesion, list[Speaker]]
# Bogotá no tiene horario de verano: un desfase fijo alcanza y no depende de tzdata.
BOGOTA = timezone(timedelta(hours=-5))
# El detail de un choque con una sesión que quien pregunta no puede ver.
SIN_SESION = "La ponente ya tiene otra sesión en ese horario"


class Sesiones(Protocol):
    def por_id(self, id_sesion: UUID) -> Sesion | None: ...
    def por_id_para_escribir(self, id_sesion: UUID) -> Sesion | None: ...
    def ponentes_de(self, ids_sesion: list[UUID]) -> dict[UUID, list[Speaker]]: ...
    def choque_de_ponentes(
        self, ids_ponente: list[UUID], inicio: datetime, fin: datetime, excluir: UUID | None
    ) -> tuple[Speaker, Sesion, Event] | None: ...
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


def _exigir_abierto(evento: Event) -> None:
    if evento.status == EstadoEvento.CANCELLED or servicio_eventos.finalizado(evento):
        raise Conflict(titulo="Un evento cancelado o finalizado no acepta cambios en sus sesiones")


def _hora(fecha: datetime, formato: str = "%H:%M") -> str:
    return fecha.astimezone(BOGOTA).strftime(formato)


def _sala(sala: str | None) -> str:
    return (sala or "").strip().casefold()


def _validar_horario(
    eventos: Eventos,
    sesiones: Sesiones,
    usuario: User,
    evento: Event,
    inicio: datetime,
    fin: datetime,
    sala: str | None,
    asignados: list[Speaker],
    excluir: UUID | None = None,
) -> None:
    """Dentro del evento, sin cruces de sus ponentes (en cualquier evento no cancelado) ni de su
    sala (en el mismo evento). `excluir` es la propia sesión al editar: no choca consigo misma.

    El choque de ponente nombra la otra sesión solo si quien pregunta puede ver su evento: un
    borrador ajeno no revela ni su título ni su horario."""
    if inicio < evento.start_at or fin > evento.end_at:
        con_dia = "%d/%m %H:%M"
        raise Conflict(
            f"El evento va del {_hora(evento.start_at, con_dia)} al {_hora(evento.end_at, con_dia)}"
            " (hora de Bogotá)",
            tipo="session-outside-event",
            titulo="La sesión no cae dentro del evento",
        )
    # La base devuelve solo la sesión que choca, no la agenda entera de los ponentes.
    choque = sesiones.choque_de_ponentes([p.id for p in asignados], inicio, fin, excluir)
    if choque is not None:
        ponente, otra, su_evento = choque
        detalle = SIN_SESION
        if servicio_eventos.puede_ver(usuario, su_evento):
            detalle = (
                f"{ponente.full_name} ya está en «{otra.title}», "
                f"{_hora(otra.start_at)} a {_hora(otra.end_at)}"
            )
        raise Conflict(
            detalle,
            tipo="speaker-conflict",
            titulo="El ponente ya tiene otra sesión en ese horario",
        )
    normalizada = _sala(sala)
    if not normalizada:  # las sesiones sin sala no chocan
        return
    for otra in eventos.sesiones_de(evento.id):
        if (
            otra.id != excluir
            and _sala(otra.room) == normalizada
            and se_cruzan(inicio, fin, otra.start_at, otra.end_at)
        ):
            raise Conflict(
                f"«{otra.title}» ocupa {sala} de {_hora(otra.start_at)} a {_hora(otra.end_at)}",
                tipo="room-conflict",
                titulo="La sala ya está ocupada en ese horario",
            )


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
    _exigir_abierto(evento)
    _validar_capacidad(evento, datos.capacity)
    asignados = _bloquear_ponentes(ponentes, datos.speaker_ids)
    sesion = Sesion(**datos.model_dump(exclude={"speaker_ids"}), event_id=evento.id)
    _validar_horario(
        eventos, sesiones, usuario, evento, sesion.start_at, sesion.end_at, sesion.room, asignados
    )
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
    _exigir_abierto(evento)
    cambios = datos.model_dump(exclude_unset=True)
    ids_nuevos = cambios.pop("speaker_ids", None)
    if cambios.get("end_at", sesion.end_at) <= cambios.get("start_at", sesion.start_at):
        raise DatosInvalidos("end_at", "Tiene que ser posterior al inicio")
    _validar_capacidad(evento, cambios.get("capacity", sesion.capacity))
    actuales = [p.id for p in sesiones.ponentes_de([sesion.id])[sesion.id]]
    asignados = _bloquear_ponentes(ponentes, actuales if ids_nuevos is None else ids_nuevos)
    # Se valida antes de tocar la sesión: si algo choca, queda como estaba.
    _validar_horario(
        eventos,
        sesiones,
        usuario,
        evento,
        cambios.get("start_at", sesion.start_at),
        cambios.get("end_at", sesion.end_at),
        cambios.get("room", sesion.room),
        asignados,
        excluir=sesion.id,
    )
    for campo, valor in cambios.items():
        setattr(sesion, campo, valor)
    ids_a_guardar = None if ids_nuevos is None else sorted(set(ids_nuevos))
    guardada = sesiones.guardar(sesion, ids_a_guardar)
    return guardada, sesiones.ponentes_de([guardada.id])[guardada.id]


def eliminar(eventos: Eventos, sesiones: Sesiones, usuario: User, id_sesion: UUID) -> None:
    evento, sesion = _para_escribir(eventos, sesiones, usuario, id_sesion)
    _exigir_abierto(evento)
    sesiones.eliminar(sesion)
