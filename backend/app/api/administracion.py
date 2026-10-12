from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencias import RepoUsuarios, UsuarioActual
from app.api.errores import respuestas_de_error
from app.api.paginacion import ParametrosPagina, parametros_pagina
from app.core.permisos import Rol
from app.schemas.administracion import (
    ContrasenaTemporal,
    FiltrosUsuarios,
    UsuarioAdmin,
    UsuarioAlta,
    UsuarioCreado,
    UsuarioEdicion,
)
from app.schemas.comunes import Pagina
from app.services import administracion
from app.services.administracion import ConInscripciones

router = APIRouter(prefix="/admin", tags=["administración"])


def _salida(con: ConInscripciones) -> UsuarioAdmin:
    return UsuarioAdmin.model_validate(
        con.usuario.model_dump() | {"active_registrations": con.inscripciones_activas}
    )


def _sin_cache(response: Response) -> None:
    """Una respuesta con una contraseña temporal no se guarda en ninguna caché: se ve una vez."""
    response.headers["Cache-Control"] = "no-store"


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


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    summary="Crear un usuario con una contraseña temporal",
    description=(
        "Solo el admin. Acepta solo `email`, `full_name` y `role` (cualquiera, también `ADMIN`): "
        "la contraseña la genera el sistema, y mandarla responde 422. La respuesta trae "
        "`temporary_password`, que no se vuelve a mostrar, y no se guarda en caché. El usuario "
        "tiene que cambiarla en su primer login. Email ya registrado: 409 `email-taken`."
    ),
    responses=respuestas_de_error(401, 403, 409, 422),
)
def crear(
    datos: UsuarioAlta, usuario: UsuarioActual, repo: RepoUsuarios, response: Response
) -> UsuarioCreado:
    creado = administracion.crear(repo, usuario, datos)
    _sin_cache(response)
    return UsuarioCreado.model_validate(
        creado.usuario.model_dump()
        | {"active_registrations": 0, "temporary_password": creado.contrasena_temporal}
    )


@router.post(
    "/users/{id_usuario}/reset-password",
    summary="Restablecer la contraseña de un usuario",
    description=(
        "Solo el admin. Genera una contraseña temporal nueva, que se devuelve una sola vez y no "
        "se guarda en caché; la anterior deja de servir y el usuario tiene que cambiarla en su "
        "próximo login. El admin no se la restablece a sí mismo (409 `cannot-modify-self`), y a "
        "un usuario desactivado tampoco (409 `user-inactive`)."
    ),
    responses=respuestas_de_error(401, 403, 404, 409),
)
def restablecer_contrasena(
    id_usuario: UUID, usuario: UsuarioActual, repo: RepoUsuarios, response: Response
) -> ContrasenaTemporal:
    temporal = administracion.restablecer_contrasena(repo, usuario, id_usuario)
    _sin_cache(response)
    return ContrasenaTemporal(temporary_password=temporal)
