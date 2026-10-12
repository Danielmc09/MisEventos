"""Inscripciones a un evento: inscribirse con control de cupo y cancelar la propia.

Lanza excepciones de dominio; no sabe nada de HTTP."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.core.excepciones import Conflict, NotFound
from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import EstadoInscripcion, Registration
from app.models.usuario import User
from app.schemas.eventos import Cuando
from app.services import eventos as servicio_eventos
from app.services.eventos import Eventos


class Inscripciones(Protocol):
    def del_usuario(
        self, id_usuario: UUID, estado: EstadoInscripcion, cuando: Cuando, offset: int, limite: int
    ) -> tuple[list[tuple[Registration, Event]], int]: ...
    def activa_de(self, id_usuario: UUID, id_evento: UUID) -> Registration | None: ...
    def crear(self, inscripcion: Registration) -> Registration: ...
    def guardar(self, inscripcion: Registration) -> Registration: ...


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
            f"El evento alcanzó su capacidad de {evento.capacity} personas.",
            tipo="capacity-full",
            titulo="El evento no tiene cupos",
        )
    return inscripciones.crear(Registration(user_id=usuario.id, event_id=evento.id))


def cancelar(
    eventos: Eventos, inscripciones: Inscripciones, usuario: User, id_evento: UUID
) -> None:
    """Cancela la inscripción activa del usuario, solo antes de que el evento empiece, y libera
    el cupo. Toma el mismo bloqueo del evento que inscribirse, en el mismo orden. Sin una
    inscripción activa propia es 404, exista o no el evento."""
    evento = eventos.por_id_para_escribir(id_evento)
    inscripcion = None if evento is None else inscripciones.activa_de(usuario.id, evento.id)
    if evento is None or inscripcion is None:
        raise NotFound()
    if servicio_eventos.ya_empezo(evento):
        raise _evento_empezado("La inscripción se puede cancelar hasta que el evento empieza.")
    inscripcion.status = EstadoInscripcion.CANCELLED
    inscripcion.cancelled_at = datetime.now(UTC)
    inscripciones.guardar(inscripcion)


def mias(
    inscripciones: Inscripciones,
    usuario: User,
    estado: EstadoInscripcion,
    cuando: Cuando,
    offset: int,
    limite: int,
) -> tuple[list[tuple[Registration, Event]], int]:
    """Las inscripciones del usuario del token, con su evento. Nunca las de otra persona."""
    return inscripciones.del_usuario(usuario.id, estado, cuando, offset, limite)


def porcentaje_de_ocupacion(activas: int, capacidad: int) -> Decimal:
    return Decimal(0)
