from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencias import RepoUsuarios, UsuarioActual
from app.api.errores import respuestas_de_error
from app.api.paginacion import ParametrosPagina, parametros_pagina
from app.core.permisos import Rol
from app.schemas.administracion import FiltrosUsuarios, UsuarioAdmin, UsuarioEdicion
from app.schemas.comunes import Pagina
from app.services import administracion
from app.services.administracion import ConInscripciones

router = APIRouter(prefix="/admin", tags=["administración"])


def _salida(con: ConInscripciones) -> UsuarioAdmin:
    return UsuarioAdmin.model_validate(
        con.usuario.model_dump() | {"active_registrations": con.inscripciones_activas}
    )


@router.get(
    "/users",
    summary="Listar y buscar usuarios",
    description=(
        "Solo el admin. Cada usuario trae sus inscripciones activas. Ordenados por email."
    ),
    responses=respuestas_de_error(401, 403, 422),
)
def listar(
    usuario: UsuarioActual,
    repo: RepoUsuarios,
    pagina: Annotated[ParametrosPagina, Depends(parametros_pagina)],
    q: Annotated[
        str | None, Query(max_length=100, description="Nombre o email, o parte de ellos")
    ] = None,
    role: Annotated[
        list[Rol] | None,
        Query(description="Solo los de estos roles; se repite para pedir varios"),
    ] = None,
    is_active: Annotated[bool | None, Query(description="Solo activos o solo inactivos")] = None,
) -> Pagina[UsuarioAdmin]:
    filtros = FiltrosUsuarios(q=q, rol=frozenset(role or ()), activo=is_active)
    items, total = administracion.listar(repo, usuario, filtros, pagina.offset, pagina.page_size)
    return Pagina[UsuarioAdmin].crear(
        [_salida(con) for con in items], total=total, page=pagina.page, page_size=pagina.page_size
    )


@router.patch(
    "/users/{id_usuario}",
    summary="Cambiar el nombre, el email, el rol o el estado de un usuario",
    description=(
        "Solo el admin. Acepta solo `full_name`, `email`, `role` e `is_active`: la contraseña no "
        "se cambia por acá (422). El email se guarda en minúsculas y sin espacios; si ya lo usa "
        "otro usuario, 409 `email-taken`. El admin no puede cambiarse el rol ni desactivarse a "
        "sí mismo (409 `cannot-modify-self`), y siempre queda al menos un admin activo (409 "
        "`last-admin`). Desactivar corta la sesión en el siguiente request."
    ),
    responses=respuestas_de_error(401, 403, 404, 409, 422),
)
def cambiar(
    id_usuario: UUID, datos: UsuarioEdicion, usuario: UsuarioActual, repo: RepoUsuarios
) -> UsuarioAdmin:
    return _salida(administracion.cambiar(repo, usuario, id_usuario, datos))
