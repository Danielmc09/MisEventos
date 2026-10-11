from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencias import RepoEventos, UsuarioActual, UsuarioOpcional
from app.api.errores import respuestas_de_error
from app.schemas.eventos import EventoEdicion, EventoEntrada, EventoSalida
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


@router.post(
    "/{id_evento}/publish",
    summary="Publicar un evento",
    description="`DRAFT → PUBLISHED`, solo si todavía no empezó. Su dueño o el admin.",
    responses=respuestas_de_error(401, 403, 404, 409, 422),
)
def publicar(id_evento: UUID, usuario: UsuarioActual, repo: RepoEventos) -> EventoSalida:
    evento = eventos.publicar(repo, usuario, id_evento)
    return EventoSalida.model_validate(evento, from_attributes=True)


@router.post(
    "/{id_evento}/unpublish",
    summary="Despublicar un evento",
    description="`PUBLISHED → DRAFT`. Su dueño o el admin.",
    responses=respuestas_de_error(401, 403, 404, 409, 422),
)
def despublicar(id_evento: UUID, usuario: UsuarioActual, repo: RepoEventos) -> EventoSalida:
    evento = eventos.despublicar(repo, usuario, id_evento)
    return EventoSalida.model_validate(evento, from_attributes=True)


@router.post(
    "/{id_evento}/cancel",
    summary="Cancelar un evento",
    description="`DRAFT | PUBLISHED → CANCELLED`, si no terminó. Es definitivo.",
    responses=respuestas_de_error(401, 403, 404, 409, 422),
)
def cancelar(id_evento: UUID, usuario: UsuarioActual, repo: RepoEventos) -> EventoSalida:
    evento = eventos.cancelar(repo, usuario, id_evento)
    return EventoSalida.model_validate(evento, from_attributes=True)


@router.patch(
    "/{id_evento}",
    summary="Editar un evento",
    description=(
        "Se manda solo lo que cambia. `status` y `organizer_id` no se aceptan. "
        "Un evento cancelado o finalizado no se edita (409). Su dueño o el admin."
    ),
    responses=respuestas_de_error(401, 403, 404, 409, 422),
)
def editar(
    id_evento: UUID, datos: EventoEdicion, usuario: UsuarioActual, repo: RepoEventos
) -> EventoSalida:
    evento = eventos.editar(repo, usuario, id_evento, datos)
    return EventoSalida.model_validate(evento, from_attributes=True)
