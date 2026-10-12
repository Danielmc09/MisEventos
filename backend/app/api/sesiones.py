from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencias import (
    RepoEventos,
    RepoPonentes,
    RepoReservas,
    RepoSesiones,
    UsuarioActual,
    UsuarioOpcional,
)
from app.api.errores import respuestas_de_error
from app.schemas.sesiones import (
    PonenteDeSesion,
    SesionConCupo,
    SesionEdicion,
    SesionEntrada,
    SesionSalida,
)
from app.services import sesiones
from app.services.sesiones import SesionConPonentes, SesionDelListado

router = APIRouter(tags=["sesiones"])


def _salida(sesion_y_ponentes: SesionConPonentes) -> SesionSalida:
    """Los ponentes, sin el email: las sesiones son públicas."""
    sesion, ponentes = sesion_y_ponentes
    return SesionSalida(
        **sesion.model_dump(),
        speakers=[PonenteDeSesion.model_validate(p, from_attributes=True) for p in ponentes],
    )


def _con_cupo(del_listado: SesionDelListado) -> SesionConCupo:
    return SesionConCupo(
        **_salida((del_listado.sesion, del_listado.ponentes)).model_dump(),
        reserved_count=del_listado.reservadas,
        available_spots=del_listado.lugares,
        is_reserved=del_listado.reservada,
    )


@router.get(
    "/events/{id_evento}/sessions",
    summary="Ver las sesiones de un evento",
    description=(
        "Público, para quien puede ver el evento (si no, 404). Ordenadas por hora de inicio, "
        "cada una con sus ponentes, sin el email, sus reservas activas, los lugares libres y "
        "si el usuario autenticado la reservó."
    ),
    responses=respuestas_de_error(404, 422),
)
def listar(
    id_evento: UUID,
    usuario: UsuarioOpcional,
    eventos: RepoEventos,
    repo: RepoSesiones,
    reservas: RepoReservas,
) -> list[SesionConCupo]:
    return [_con_cupo(s) for s in sesiones.listar(eventos, repo, reservas, usuario, id_evento)]


@router.post(
    "/events/{id_evento}/sessions",
    status_code=status.HTTP_201_CREATED,
    summary="Crear una sesión",
    description=(
        "El dueño del evento o el admin. Tiene que caer dentro del evento y no cruzarse con "
        "otra sesión de sus ponentes ni de su sala (409)."
    ),
    responses=respuestas_de_error(401, 403, 404, 409, 422),
)
def crear(
    id_evento: UUID,
    datos: SesionEntrada,
    usuario: UsuarioActual,
    eventos: RepoEventos,
    repo: RepoSesiones,
    ponentes: RepoPonentes,
) -> SesionSalida:
    return _salida(sesiones.crear(eventos, repo, ponentes, usuario, id_evento, datos))


@router.patch(
    "/sessions/{id_sesion}",
    summary="Editar una sesión",
    description=(
        "Se manda solo lo que cambia; `speaker_ids`, si viene, reemplaza la lista. "
        "Con reservas activas, el horario no cambia (`session-has-reservations`) y la capacidad "
        "no baja de lo reservado (`capacity-below-reservations`). El dueño del evento o el admin."
    ),
    responses=respuestas_de_error(401, 403, 404, 409, 422),
)
def editar(
    id_sesion: UUID,
    datos: SesionEdicion,
    usuario: UsuarioActual,
    eventos: RepoEventos,
    repo: RepoSesiones,
    ponentes: RepoPonentes,
    reservas: RepoReservas,
) -> SesionSalida:
    return _salida(sesiones.editar(eventos, repo, ponentes, reservas, usuario, id_sesion, datos))


@router.delete(
    "/sessions/{id_sesion}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una sesión",
    description=(
        "El dueño del evento o el admin. Con reservas activas no se elimina "
        "(`session-has-reservations`)."
    ),
    responses=respuestas_de_error(401, 403, 404, 409, 422),
)
def eliminar(
    id_sesion: UUID,
    usuario: UsuarioActual,
    eventos: RepoEventos,
    repo: RepoSesiones,
    reservas: RepoReservas,
) -> None:
    sesiones.eliminar(eventos, repo, reservas, usuario, id_sesion)
