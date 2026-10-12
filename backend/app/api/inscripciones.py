from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, status

from app.api.dependencias import RepoEventos, RepoInscripciones, UsuarioActual
from app.api.errores import respuestas_de_error
from app.schemas.inscripciones import InscripcionEntrada, InscripcionSalida
from app.services import inscripciones

router = APIRouter(tags=["inscripciones"])


@router.post(
    "/events/{id_evento}/registrations",
    status_code=status.HTTP_201_CREATED,
    summary="Inscribirse a un evento",
    description=(
        "El usuario actual se inscribe a un evento publicado que todavía no empezó, si queda "
        "cupo. 409 con `event-not-open`, `event-started`, `already-registered` o "
        "`capacity-full`, en ese orden."
    ),
    responses=respuestas_de_error(401, 404, 409, 422),
)
def inscribirse(
    id_evento: UUID,
    usuario: UsuarioActual,
    eventos: RepoEventos,
    repo: RepoInscripciones,
    # Opcional y sin campos: no se usa, pero un campo desconocido responde 422.
    datos: Annotated[InscripcionEntrada, Body(default_factory=InscripcionEntrada)],
) -> InscripcionSalida:
    inscripcion = inscripciones.inscribirse(eventos, repo, usuario, id_evento)
    return InscripcionSalida.model_validate(inscripcion, from_attributes=True)


@router.delete(
    "/events/{id_evento}/registrations/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancelar mi inscripción",
    description=(
        "Cancela la inscripción activa del usuario actual, que sale del token. Solo antes de que "
        "el evento empiece (409 `event-started`); sin inscripción activa, 404. Libera el cupo."
    ),
    responses=respuestas_de_error(401, 404, 409, 422),
)
def cancelar(
    id_evento: UUID, usuario: UsuarioActual, eventos: RepoEventos, repo: RepoInscripciones
) -> None:
    inscripciones.cancelar(eventos, repo, usuario, id_evento)
