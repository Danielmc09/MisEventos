"""Reservas de lugar en una sesión: reservar con control de capacidad y sin cruces dentro del
evento.

Lanza excepciones de dominio; no sabe nada de HTTP.

Orden de los bloqueos (`SELECT … FOR UPDATE`), el mismo en todo el sistema:

    evento → inscripción → sesión → ponentes

Todo camino que toma más de una de esas filas las toma en ese orden y nunca al revés, así dos
transacciones no se esperan en círculo:
- reservar y cancelar una reserva: evento, la inscripción activa del usuario y la sesión;
- cancelar la inscripción al evento (con la cascada sobre sus reservas): evento e inscripción;
- inscribirse: evento;
- crear, editar o eliminar una sesión: evento, sesión y ponentes.

Bloquear la inscripción ordena las reservas del mismo usuario en el evento (dos reservas suyas a la
vez a sesiones que se cruzan no pasan las dos) y garantiza que siga activa mientras se reserva.
Bloquear la sesión ordena a todos los que piden su último lugar."""

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.core.excepciones import Conflict, NotFound
from app.core.textos import plural
from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import Registration
from app.models.reserva import EstadoReserva, SessionRegistration
from app.models.sesion import Session as Sesion
from app.models.usuario import User
from app.services import eventos as servicio_eventos
from app.services.eventos import Eventos
from app.services.sesiones import BOGOTA, Sesiones, capacidad_efectiva


class Reservas(Protocol):
    def activa_de(self, id_usuario: UUID, id_sesion: UUID) -> SessionRegistration | None: ...
    def activas_en(self, id_sesion: UUID) -> int: ...
    def cruces(
        self, id_usuario: UUID, id_evento: UUID, inicio: datetime, fin: datetime
    ) -> list[Sesion]: ...
    def crear(self, reserva: SessionRegistration) -> SessionRegistration: ...
    def guardar(self, reserva: SessionRegistration) -> SessionRegistration: ...


class InscripcionesParaReservar(Protocol):
    def activa_para_escribir(self, id_usuario: UUID, id_evento: UUID) -> Registration | None: ...


def _bloquear(
    eventos: Eventos,
    sesiones: Sesiones,
    inscripciones: InscripcionesParaReservar,
    usuario: User,
    id_sesion: UUID,
) -> tuple[Event, Registration | None, Sesion]:
    """El evento, la inscripción activa del usuario (si tiene) y la sesión, bloqueados en ese
    orden. Una sesión inexistente, o de un evento que el usuario no ve, es 404."""
    sesion = sesiones.por_id(id_sesion)
    if sesion is None:
        raise NotFound()
    evento = eventos.por_id_para_escribir(sesion.event_id)
    if evento is None or not servicio_eventos.puede_ver(usuario, evento):
        raise NotFound()
    inscripcion = inscripciones.activa_para_escribir(usuario.id, evento.id)
    sesion = sesiones.por_id_para_escribir(id_sesion)
    if sesion is None:  # la borraron mientras se esperaba el bloqueo del evento
        raise NotFound()
    return evento, inscripcion, sesion


def _empezo(sesion: Sesion) -> bool:
    return sesion.start_at <= datetime.now(UTC)


def _sesion_empezada(detalle: str) -> Conflict:
    return Conflict(detalle, tipo="session-started", titulo="La sesión ya empezó")


def _hora(fecha: datetime) -> str:
    return fecha.astimezone(BOGOTA).strftime("%H:%M")


def _choque(cruces: list[Sesion]) -> Conflict:
    lineas = [
        f"Ya reservaste «{s.title}», {_hora(s.start_at)} a {_hora(s.end_at)}"
        + (f", {s.room}" if s.room else "")
        for s in cruces
    ]
    conflictos = [
        {
            "session_id": s.id,
            "title": s.title,
            "start_at": s.start_at.astimezone(UTC),
            "end_at": s.end_at.astimezone(UTC),
            "room": s.room,
        }
        for s in cruces
    ]
    return Conflict(
        "\n".join(lineas),
        tipo="session-conflict",
        titulo="La sesión se cruza con otra que ya reservaste",
        extensiones={"conflicts": conflictos},
    )


def reservar(
    eventos: Eventos,
    sesiones: Sesiones,
    inscripciones: InscripcionesParaReservar,
    reservas: Reservas,
    usuario: User,
    id_sesion: UUID,
) -> SessionRegistration:
    """Las reglas van en orden y la primera que falla define el error. El cruce va último: no
    tiene sentido hablar de un cruce si de todas formas no hay lugar."""
    evento, inscripcion, sesion = _bloquear(eventos, sesiones, inscripciones, usuario, id_sesion)
    if evento.status != EstadoEvento.PUBLISHED:
        raise Conflict(
            "Solo se reservan sesiones de un evento publicado.",
            tipo="event-not-open",
            titulo="El evento no admite reservas",
        )
    if _empezo(sesion):
        raise _sesion_empezada("Las reservas cierran cuando la sesión empieza.")
    if inscripcion is None:
        raise Conflict(
            "Reservar una sesión exige una inscripción activa al evento.",
            tipo="not-registered",
            titulo="Inscribite al evento para reservar sesiones",
        )
    if reservas.activa_de(usuario.id, sesion.id) is not None:
        raise Conflict(
            "Ya tenés una reserva activa en esta sesión.",
            tipo="already-reserved",
            titulo="Ya reservaste esta sesión",
        )
    capacidad = capacidad_efectiva(sesion, evento)
    if reservas.activas_en(sesion.id) >= capacidad:
        raise Conflict(
            f"La sesión alcanzó su capacidad de {plural(capacidad, 'persona', 'personas')}.",
            tipo="session-full",
            titulo="La sesión no tiene lugares",
        )
    cruces = reservas.cruces(usuario.id, evento.id, sesion.start_at, sesion.end_at)
    if cruces:
        raise _choque(cruces)
    return reservas.crear(SessionRegistration(user_id=usuario.id, session_id=sesion.id))


def cancelar(
    eventos: Eventos,
    sesiones: Sesiones,
    inscripciones: InscripcionesParaReservar,
    reservas: Reservas,
    usuario: User,
    id_sesion: UUID,
) -> None:
    """Cancela la reserva activa del usuario, solo antes de que la sesión empiece, y libera el
    lugar. Toma los mismos bloqueos que reservar, en el mismo orden. Sin una reserva activa
    propia es 404, aunque la sesión ya haya empezado."""
    _, _, sesion = _bloquear(eventos, sesiones, inscripciones, usuario, id_sesion)
    reserva = reservas.activa_de(usuario.id, sesion.id)
    if reserva is None:
        raise NotFound()
    if _empezo(sesion):
        raise _sesion_empezada("La reserva se puede cancelar hasta que la sesión empieza.")
    reserva.status = EstadoReserva.CANCELLED
    reserva.cancelled_at = datetime.now(UTC)
    reservas.guardar(reserva)
