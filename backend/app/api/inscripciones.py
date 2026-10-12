from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status

from app.api.dependencias import RepoEventos, RepoInscripciones, RepoReservas, UsuarioActual
from app.api.errores import respuestas_de_error
from app.api.paginacion import ParametrosPagina, parametros_pagina
from app.models.inscripcion import EstadoInscripcion
from app.schemas.comunes import Pagina
from app.schemas.eventos import Cuando
from app.schemas.inscripciones import (
    EstadisticasSalida,
    InscripcionEntrada,
    InscripcionMia,
    InscripcionSalida,
    Inscrito,
    ResumenEvento,
)
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
        "el evento empiece (409 `event-started`); sin inscripción activa, 404. Libera el cupo "
        "y cancela sus reservas de sesiones en ese evento."
    ),
    responses=respuestas_de_error(401, 404, 409, 422),
)
def cancelar(
    id_evento: UUID,
    usuario: UsuarioActual,
    eventos: RepoEventos,
    repo: RepoInscripciones,
    reservas: RepoReservas,
) -> None:
    inscripciones.cancelar(eventos, repo, reservas, usuario, id_evento)


@router.get(
    "/me/registrations",
    summary="Mis inscripciones",
    description=(
        "Las inscripciones del usuario actual, cada una con el resumen de su evento. Por "
        "defecto, las activas de eventos que no terminaron."
    ),
    responses=respuestas_de_error(401, 422),
)
def mias(
    usuario: UsuarioActual,
    repo: RepoInscripciones,
    pagina: Annotated[ParametrosPagina, Depends(parametros_pagina)],
    estado: Annotated[
        EstadoInscripcion, Query(alias="status", description="`ACTIVE` o `CANCELLED`")
    ] = EstadoInscripcion.ACTIVE,
    when: Annotated[Cuando, Query(description="`upcoming` o `past`")] = Cuando.UPCOMING,
) -> Pagina[InscripcionMia]:
    filas, total = inscripciones.mias(repo, usuario, estado, when, pagina.offset, pagina.page_size)
    items = [
        InscripcionMia.model_validate(
            inscripcion.model_dump()
            | {"event": ResumenEvento.model_validate(evento, from_attributes=True)}
        )
        for inscripcion, evento in filas
    ]
    return Pagina[InscripcionMia].crear(
        items, total=total, page=pagina.page, page_size=pagina.page_size
    )


@router.get(
    "/events/{id_evento}/registrations",
    summary="Inscritos de un evento",
    description=(
        "Una página de los inscritos, activos y cancelados, con su nombre y email. Solo el "
        "dueño del evento o el admin; un borrador que no puede ver, 404."
    ),
    responses=respuestas_de_error(401, 403, 404, 422),
)
def inscritos(
    id_evento: UUID,
    usuario: UsuarioActual,
    eventos: RepoEventos,
    repo: RepoInscripciones,
    pagina: Annotated[ParametrosPagina, Depends(parametros_pagina)],
) -> Pagina[Inscrito]:
    filas, total = inscripciones.inscritos_del_evento(
        eventos, repo, usuario, id_evento, pagina.offset, pagina.page_size
    )
    items = [
        Inscrito(
            full_name=persona.full_name,
            email=persona.email,
            status=inscripcion.status,
            created_at=inscripcion.created_at,
        )
        for inscripcion, persona in filas
    ]
    return Pagina[Inscrito].crear(items, total=total, page=pagina.page, page_size=pagina.page_size)


@router.get(
    "/events/{id_evento}/stats",
    summary="Estadísticas de un evento",
    description=(
        "Inscripciones activas y canceladas, cupos libres y porcentaje de ocupación (un "
        "decimal). Solo el dueño del evento o el admin."
    ),
    responses=respuestas_de_error(401, 403, 404, 422),
)
def estadisticas(
    id_evento: UUID, usuario: UsuarioActual, eventos: RepoEventos, repo: RepoInscripciones
) -> EstadisticasSalida:
    cifras = inscripciones.estadisticas(eventos, repo, usuario, id_evento)
    return EstadisticasSalida.model_validate(cifras, from_attributes=True)
