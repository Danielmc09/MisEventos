from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencias import RepoEventos, UsuarioActual, UsuarioOpcional
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


@router.get(
    "/{id_evento}",
    summary="Ver un evento",
    description="Público. Un borrador solo lo ven su dueño y el admin; para el resto, 404.",
    responses=respuestas_de_error(404, 422),
)
def ver(id_evento: UUID, usuario: UsuarioOpcional, repo: RepoEventos) -> EventoSalida:
    evento = eventos.obtener(repo, usuario, id_evento)
    return EventoSalida.model_validate(evento, from_attributes=True)
