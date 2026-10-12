from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencias import RepoEventos, UsuarioActual, UsuarioOpcional
from app.api.errores import respuestas_de_error
from app.api.paginacion import ParametrosPagina, parametros_pagina
from app.models.evento import EstadoEvento
from app.schemas.comunes import FechaUTC, Pagina, Texto
from app.schemas.eventos import (
    Cuando,
    EventoEdicion,
    EventoEntrada,
    EventoSalida,
    FiltrosEventos,
    OrdenEventos,
)
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
    "",
    summary="Listar y buscar eventos",
    description=(
        "Público. Solo trae lo que quien pregunta puede ver: un borrador, solo su dueño y el "
        "admin. Por defecto, los que no terminaron, ordenados por fecha de inicio."
    ),
    responses=respuestas_de_error(422),
)
def listar(
    usuario: UsuarioOpcional,
    repo: RepoEventos,
    pagina: Annotated[ParametrosPagina, Depends(parametros_pagina)],
    q: Annotated[
        Texto | None, Query(max_length=100, description="Nombre o parte del nombre")
    ] = None,
    estados: Annotated[
        list[EstadoEvento] | None, Query(alias="status", description="Uno o varios estados")
    ] = None,
    desde: Annotated[
        FechaUTC | None, Query(alias="from", description="Empieza desde, con zona")
    ] = None,
    hasta: Annotated[
        FechaUTC | None, Query(alias="to", description="Empieza hasta, con zona")
    ] = None,
    when: Annotated[Cuando, Query(description="`upcoming` o `past`")] = Cuando.UPCOMING,
    order_by: Annotated[
        OrdenEventos, Query(description="`start_at`, `-start_at` o `name`")
    ] = OrdenEventos.START_AT,
) -> Pagina[EventoSalida]:
    filtros = FiltrosEventos(
        q=q, estados=estados, desde=desde, hasta=hasta, cuando=when, orden=order_by
    )
    items, total = eventos.listar(repo, usuario, filtros, pagina.offset, pagina.page_size)
    return Pagina[EventoSalida].crear(
        [EventoSalida.model_validate(e, from_attributes=True) for e in items],
        total=total,
        page=pagina.page,
        page_size=pagina.page_size,
    )


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


@router.delete(
    "/{id_evento}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un evento",
    description="Lo borra de forma definitiva. Su dueño o el admin.",
    responses=respuestas_de_error(401, 403, 404, 409, 422),
)
def eliminar(id_evento: UUID, usuario: UsuarioActual, repo: RepoEventos) -> None:
    eventos.eliminar(repo, usuario, id_evento)
