"""Sesiones de un evento: las ve quien ve el evento; las gestionan su dueño o el admin.

Lanza excepciones de dominio; no sabe nada de HTTP."""

from dataclasses import dataclass
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


class Sesiones(Protocol):
    def por_id(self, id_sesion: UUID) -> Sesion | None: ...
    def por_id_para_escribir(self, id_sesion: UUID) -> Sesion | None: ...
    def ponentes_de(self, ids_sesion: list[UUID]) -> dict[UUID, list[Speaker]]: ...
    def choques_de_ponentes(
        self, ids_ponente: list[UUID], inicio: datetime, fin: datetime, excluir: UUID | None
    ) -> list[tuple[Speaker, Sesion, Event]]: ...
    def crear(self, sesion: Sesion, ids_ponente: list[UUID]) -> Sesion: ...
    def guardar(self, sesion: Sesion, ids_ponente: list[UUID] | None) -> Sesion: ...
    def eliminar(self, sesion: Sesion) -> None: ...


class OcupacionDeSesiones(Protocol):
    def ocupacion(
        self, ids_sesion: list[UUID], id_usuario: UUID | None
    ) -> dict[UUID, tuple[int, bool]]: ...


def capacidad_efectiva(sesion: Sesion, evento: Event) -> int:
    """La capacidad propia de la sesión o, si no tiene, la del evento."""
    return sesion.capacity if sesion.capacity is not None else evento.capacity


@dataclass(frozen=True)
class SesionDelListado:
    sesion: Sesion
    ponentes: list[Speaker]
    reservadas: int
    lugares: int
    reservada: bool  # por quien pregunta; un anónimo no tiene reservas


def listar(
    eventos: Eventos,
    sesiones: Sesiones,
    reservas: OcupacionDeSesiones,
    usuario: User | None,
    id_evento: UUID,
) -> list[SesionDelListado]:
    """Las sesiones por hora de inicio, cada una con sus reservas activas y sus lugares libres.
    Los ponentes y las reservas se piden una sola vez para todas. Si no puede ver el evento,
    NotFound."""
    evento = servicio_eventos.obtener(eventos, usuario, id_evento)
    propias = eventos.sesiones_de(evento.id)
    ids = [s.id for s in propias]
    ponentes = sesiones.ponentes_de(ids)
    ocupacion = reservas.ocupacion(ids, None if usuario is None else usuario.id)
    listado = []
    for sesion in propias:
        reservadas, reservada = ocupacion[sesion.id]
        listado.append(
            SesionDelListado(
                sesion=sesion,
                ponentes=ponentes[sesion.id],
                reservadas=reservadas,
                lugares=capacidad_efectiva(sesion, evento) - reservadas,
                reservada=reservada,
            )
        )
    return listado


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


def _linea_de_choque(usuario: User, ponente: Speaker, otra: Sesion, su_evento: Event) -> str:
    if not servicio_eventos.puede_ver(usuario, su_evento):
        return f"{ponente.full_name} ya tiene otra sesión en ese horario"
    return (
        f"{ponente.full_name} ya está en «{otra.title}», "
        f"{_hora(otra.start_at)} a {_hora(otra.end_at)}"
    )


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

    El choque de ponente lista a cada ponente ocupado, uno por línea. Nombra la otra sesión solo
    si quien pregunta puede ver su evento: un borrador ajeno no revela su título ni su horario."""
    if inicio < evento.start_at or fin > evento.end_at:
        con_dia = "%d/%m %H:%M"
        raise Conflict(
            f"El evento va del {_hora(evento.start_at, con_dia)} al {_hora(evento.end_at, con_dia)}"
            " (hora de Bogotá)",
            tipo="session-outside-event",
            titulo="La sesión no cae dentro del evento",
        )
    # La base devuelve solo la primera sesión que choca de cada ponente, no su agenda entera.
    choques = sesiones.choques_de_ponentes([p.id for p in asignados], inicio, fin, excluir)
    if choques:
        en_orden = sorted(choques, key=lambda c: (c[0].full_name, c[0].id))
        raise Conflict(
            "\n".join(_linea_de_choque(usuario, *choque) for choque in en_orden),
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
