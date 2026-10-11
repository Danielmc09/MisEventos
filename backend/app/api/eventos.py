from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencias import RepoEventos, UsuarioActual
from app.api.errores import respuestas_de_error
from app.schemas.eventos import EventoEntrada, EventoSalida
from app.services import eventos

router = APIRouter(prefix="/events", tags=["eventos"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Crear un evento",
    description="Lo crea en borrador (`DRAFT`), a nombre del usuario actual.",
    responses=respuestas_de_error(401, 403, 422),
)
def crear(datos: EventoEntrada, usuario: UsuarioActual, repo: RepoEventos) -> EventoSalida:
    evento = eventos.crear(repo, usuario, datos)
    return EventoSalida.model_validate(evento, from_attributes=True)


@router.get("/{id_evento}")
def ver(id_evento: UUID) -> None:
    raise NotImplementedError
