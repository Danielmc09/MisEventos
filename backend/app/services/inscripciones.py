"""Inscripciones a un evento: inscribirse con control de cupo y cancelar la propia.

Lanza excepciones de dominio; no sabe nada de HTTP."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol
from uuid import UUID

from app.core.excepciones import Conflict, NotFound
from app.core.textos import plural
from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import EstadoInscripcion, Registration
from app.models.sesion import Session as Sesion
from app.models.usuario import User
from app.schemas.eventos import Cuando
from app.services import eventos as servicio_eventos
from app.services.eventos import Eventos
from app.services.sesiones import OcupacionDeSesiones, capacidad_efectiva


class Inscripciones(Protocol):
    def del_evento(
        self, id_evento: UUID, offset: int, limite: int
    ) -> tuple[list[tuple[Registration, User]], int]: ...
    def por_estado(self, id_evento: UUID) -> dict[EstadoInscripcion, int]: ...
    def del_usuario(
        self, id_usuario: UUID, estado: EstadoInscripcion, cuando: Cuando, offset: int, limite: int
    ) -> tuple[list[tuple[Registration, Event]], int]: ...
    def activa_de(self, id_usuario: UUID, id_evento: UUID) -> Registration | None: ...
    def activa_para_escribir(self, id_usuario: UUID, id_evento: UUID) -> Registration | None: ...
    def crear(self, inscripcion: Registration) -> Registration: ...
    def guardar(self, inscripcion: Registration) -> Registration: ...


class ReservasDelEvento(Protocol):
    def cancelar_del_evento(self, id_usuario: UUID, id_evento: UUID, cuando: datetime) -> None: ...


class ReservasDelUsuario(Protocol):
    def reservadas_por_evento(
        self, id_usuario: UUID, ids_evento: list[UUID]
    ) -> dict[UUID, list[Sesion]]: ...


InscripcionConReservas = tuple[Registration, Event, list[Sesion]]


def _evento_empezado(detalle: str) -> Conflict:
    return Conflict(detalle, tipo="event-started", titulo="El evento ya empezó")


def inscribirse(
    eventos: Eventos, inscripciones: Inscripciones, usuario: User, id_evento: UUID
) -> Registration:
    """Las reglas van en orden y la primera que falla define el error. La fila del evento queda
    bloqueada hasta el fin de la transacción: dos pedidos por el último cupo se ordenan, y el
    segundo cuenta ya con la inscripción del primero."""
    evento = eventos.por_id_para_escribir(id_evento)
    if evento is None or not servicio_eventos.puede_ver(usuario, evento):
        raise NotFound()
    if evento.status != EstadoEvento.PUBLISHED:
        raise Conflict(
            "Solo se puede inscribir a un evento publicado.",
            tipo="event-not-open",
            titulo="El evento no admite inscripciones",
        )
    if servicio_eventos.ya_empezo(evento):
        raise _evento_empezado("Las inscripciones cierran cuando el evento empieza.")
    if inscripciones.activa_de(usuario.id, evento.id) is not None:
        raise Conflict(
            "Ya tenés una inscripción activa en este evento.",
            tipo="already-registered",
            titulo="Ya estás inscrito en este evento",
        )
    if eventos.inscritos([evento.id])[evento.id] >= evento.capacity:
        raise Conflict(
            f"El evento alcanzó su capacidad de {plural(evento.capacity, 'persona', 'personas')}.",
            tipo="capacity-full",
            titulo="El evento no tiene cupos",
        )
    return inscripciones.crear(Registration(user_id=usuario.id, event_id=evento.id))


def cancelar(
    eventos: Eventos,
    inscripciones: Inscripciones,
    reservas: ReservasDelEvento,
    usuario: User,
    id_evento: UUID,
) -> None:
    """Cancela la inscripción activa del usuario, solo antes de que el evento empiece, y libera
    el cupo. En la misma transacción cancela sus reservas de sesiones en ese evento. Sin una
    inscripción activa propia es 404, exista o no el evento.

    Bloquea primero el evento y después la inscripción, el orden de todo el sistema: una reserva
    del mismo usuario que llega a la vez espera a que esto termine y encuentra la inscripción ya
    cancelada, así que no queda ninguna reserva activa colgando de ella."""
    evento = eventos.por_id_para_escribir(id_evento)
    inscripcion = (
        None if evento is None else inscripciones.activa_para_escribir(usuario.id, evento.id)
    )
    if evento is None or inscripcion is None:
        raise NotFound()
    if servicio_eventos.ya_empezo(evento):
        raise _evento_empezado("La inscripción se puede cancelar hasta que el evento empieza.")
    ahora = datetime.now(UTC)
    inscripcion.status = EstadoInscripcion.CANCELLED
    inscripcion.cancelled_at = ahora
    inscripciones.guardar(inscripcion)
    reservas.cancelar_del_evento(usuario.id, evento.id, ahora)


def mias(
    inscripciones: Inscripciones,
    reservas: ReservasDelUsuario,
    usuario: User,
    estado: EstadoInscripcion,
    cuando: Cuando,
    offset: int,
    limite: int,
) -> tuple[list[InscripcionConReservas], int]:
    """Las inscripciones del usuario del token, con su evento. Nunca las de otra persona.

    Cada inscripción activa trae las sesiones que el usuario tiene reservadas en ese evento,
    pedidas una sola vez para toda la página. Una cancelada no trae ninguna: las reservas
    activas que haya en ese evento cuelgan de su inscripción activa, no de la cancelada."""
    filas, total = inscripciones.del_usuario(usuario.id, estado, cuando, offset, limite)
    activas = [i.event_id for i, _ in filas if i.status == EstadoInscripcion.ACTIVE]
    reservadas = reservas.reservadas_por_evento(usuario.id, activas)
    con_reservas = [
        (i, e, reservadas[i.event_id] if i.status == EstadoInscripcion.ACTIVE else [])
        for i, e in filas
    ]
    return con_reservas, total


def porcentaje_de_ocupacion(activas: int, capacidad: int) -> Decimal:
    """activas / capacidad × 100, en Decimal y redondeado a un decimal (la mitad, hacia arriba)."""
    porcentaje = Decimal(activas) * 100 / Decimal(capacidad)
    return porcentaje.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def inscritos_del_evento(
    eventos: Eventos,
    inscripciones: Inscripciones,
    usuario: User,
    id_evento: UUID,
    offset: int,
    limite: int,
) -> tuple[list[tuple[Registration, User]], int]:
    """Una página de los inscritos, activos y cancelados, con su email: solo para el dueño del
    evento o el admin."""
    evento = servicio_eventos.para_gestionar(eventos, usuario, id_evento)
    return inscripciones.del_evento(evento.id, offset, limite)


@dataclass(frozen=True)
class OcupacionDeSesion:
    id: UUID
    title: str
    reserved: int
    capacity: int  # la efectiva
    occupancy_pct: Decimal


@dataclass(frozen=True)
class Estadisticas:
    active: int
    cancelled: int
    capacity: int
    available_spots: int
    occupancy_pct: Decimal
    sessions: list[OcupacionDeSesion]


def estadisticas(
    eventos: Eventos,
    inscripciones: Inscripciones,
    reservas: OcupacionDeSesiones,
    usuario: User,
    id_evento: UUID,
) -> Estadisticas:
    """Las cifras del evento y la ocupación de cada sesión, por hora de inicio, solo para su
    dueño o el admin. Las reservas de todas las sesiones se piden una sola vez."""
    evento = servicio_eventos.para_gestionar(eventos, usuario, id_evento)
    cuantas = inscripciones.por_estado(evento.id)
    activas = cuantas[EstadoInscripcion.ACTIVE]
    propias = eventos.sesiones_de(evento.id)
    ocupacion = reservas.ocupacion([s.id for s in propias], None)
    por_sesion = []
    for sesion in propias:
        reservadas, _ = ocupacion[sesion.id]
        capacidad = capacidad_efectiva(sesion, evento)
        por_sesion.append(
            OcupacionDeSesion(
                id=sesion.id,
                title=sesion.title,
                reserved=reservadas,
                capacity=capacidad,
                occupancy_pct=porcentaje_de_ocupacion(reservadas, capacidad),
            )
        )
    return Estadisticas(
        active=activas,
        cancelled=cuantas[EstadoInscripcion.CANCELLED],
        capacity=evento.capacity,
        available_spots=evento.capacity - activas,
        occupancy_pct=porcentaje_de_ocupacion(activas, evento.capacity),
        sessions=por_sesion,
    )
