from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencias import RepoPonentes, UsuarioActual
from app.api.errores import respuestas_de_error
from app.api.paginacion import ParametrosPagina, parametros_pagina
from app.models.ponente import Speaker
from app.models.usuario import User
from app.schemas.comunes import Pagina
from app.schemas.ponentes import PonenteEdicion, PonenteEntrada, PonenteSalida
from app.services import ponentes

router = APIRouter(prefix="/speakers", tags=["ponentes"])


def _salida(ponente: Speaker, usuario: User) -> PonenteSalida:
    """Sin el email si no puede verlo. Por eso cada ruta responde con exclude_unset."""
    return PonenteSalida.de(ponente, con_email=ponentes.puede_gestionar(usuario, ponente))


@router.get(
    "",
    summary="Buscar ponentes",
    description=(
        "Organizadores y admin. Busca por nombre, sin distinguir mayúsculas. El `email` solo "
        "aparece para quien creó el ponente y para el admin."
    ),
    responses=respuestas_de_error(401, 403, 422),
    response_model_exclude_unset=True,
)
def buscar(
    usuario: UsuarioActual,
    repo: RepoPonentes,
    pagina: Annotated[ParametrosPagina, Depends(parametros_pagina)],
    q: Annotated[str | None, Query(max_length=100, description="Nombre o parte del nombre")] = None,
) -> Pagina[PonenteSalida]:
    items, total = ponentes.buscar(repo, usuario, q, pagina.offset, pagina.page_size)
    return Pagina[PonenteSalida].crear(
        [_salida(p, usuario) for p in items],
        total=total,
        page=pagina.page,
        page_size=pagina.page_size,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Crear un ponente",
    description="Organizadores y admin. Queda a nombre de quien lo crea.",
    responses=respuestas_de_error(401, 403, 422),
    response_model_exclude_unset=True,
)
def crear(datos: PonenteEntrada, usuario: UsuarioActual, repo: RepoPonentes) -> PonenteSalida:
    return _salida(ponentes.crear(repo, usuario, datos), usuario)


@router.patch(
    "/{id_ponente}",
    summary="Editar un ponente",
    description="Se manda solo lo que cambia. Quien lo creó o el admin.",
    responses=respuestas_de_error(401, 403, 404, 422),
    response_model_exclude_unset=True,
)
def editar(
    id_ponente: UUID, datos: PonenteEdicion, usuario: UsuarioActual, repo: RepoPonentes
) -> PonenteSalida:
    return _salida(ponentes.editar(repo, usuario, id_ponente, datos), usuario)


@router.delete(
    "/{id_ponente}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un ponente",
    description="Quien lo creó o el admin. Si tiene sesiones asignadas, 409.",
    responses=respuestas_de_error(401, 403, 404, 409, 422),
)
def eliminar(id_ponente: UUID, usuario: UsuarioActual, repo: RepoPonentes) -> None:
    ponentes.eliminar(repo, usuario, id_ponente)
