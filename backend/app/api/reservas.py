from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, status

from app.api.dependencias import (
    RepoEventos,
    RepoInscripciones,
    RepoReservas,
    RepoSesiones,
    UsuarioActual,
)
from app.api.errores import respuestas_de_error
from app.schemas.reservas import ReservaEntrada, ReservaSalida
from app.services import reservas

router = APIRouter(tags=["reservas"])


@router.post(
    "/sessions/{id_sesion}/reservations",
    status_code=status.HTTP_201_CREATED,
    summary="Reservar un lugar en una sesión",
    description=(
        "El usuario actual, inscrito al evento, reserva un lugar en una sesión que todavía no "
        "empezó. 409 con `event-not-open`, `session-started`, `not-registered`, "
        "`already-reserved`, `session-full` o `session-conflict`, en ese orden. "
        "`session-conflict` trae en `conflicts` las sesiones propias del mismo evento que se "
        "cruzan: es un bloqueo, no se confirma."
    ),
    responses=respuestas_de_error(401, 404, 409, 422),
)
def reservar(
    id_sesion: UUID,
    usuario: UsuarioActual,
    eventos: RepoEventos,
    sesiones: RepoSesiones,
    inscripciones: RepoInscripciones,
    repo: RepoReservas,
    # Opcional y sin campos: no se usa, pero un campo desconocido responde 422.
    datos: Annotated[ReservaEntrada, Body(default_factory=ReservaEntrada)],
) -> ReservaSalida:
    reserva = reservas.reservar(eventos, sesiones, inscripciones, repo, usuario, id_sesion)
    return ReservaSalida.model_validate(reserva, from_attributes=True)
