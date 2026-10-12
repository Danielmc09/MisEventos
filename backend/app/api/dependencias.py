from typing import Annotated

from fastapi import Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordBearer
from starlette.datastructures import ImmutableMultiDict

from app.core.config import Settings
from app.core.db import SesionDB
from app.core.excepciones import Unauthorized
from app.models.usuario import User
from app.repositories.eventos import RepositorioEventos
from app.repositories.ponentes import RepositorioPonentes
from app.repositories.sesiones import RepositorioSesiones
from app.repositories.usuarios import RepositorioUsuarios
from app.schemas.comunes import CARACTER_NULO, MENSAJE_CARACTER_NULO
from app.services import autenticacion

# auto_error=False: la falta de token la responde el handler de dominio, como cualquier 401.
esquema_bearer = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _rechazar_caracter_nulo(lugar: str, datos: ImmutableMultiDict) -> None:
    errores = [
        {
            "type": "value_error",
            "loc": (lugar, nombre),
            "msg": MENSAJE_CARACTER_NULO,
            "input": valor,
        }
        for nombre, valor in datos.multi_items()
        if isinstance(valor, str) and CARACTER_NULO in valor
    ]
    if errores:
        raise RequestValidationError(errores)


# Las dos revisiones cortan antes de la validación del endpoint: un 422 por el carácter nulo no se
# junta con los demás errores de la entrada, que aparecen recién cuando el nulo se saca. Se acepta.


async def sin_caracter_nulo(request: Request) -> None:
    """Dependencia de toda la app: rechaza el carácter nulo en la query. No lee el cuerpo: los
    JSON los cubre EntradaBase y los formularios, `formulario_sin_caracter_nulo`."""
    _rechazar_caracter_nulo("query", request.query_params)


async def formulario_sin_caracter_nulo(request: Request) -> None:
    """Para los endpoints que declaran un formulario, en sus `dependencies`: rechaza el carácter
    nulo en todos sus campos. FastAPI ya parseó el formulario para el endpoint y Starlette lo
    guarda en el request, así que esto no lo vuelve a leer."""
    _rechazar_caracter_nulo("body", await request.form())


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def repositorio_usuarios(session: SesionDB) -> RepositorioUsuarios:
    return RepositorioUsuarios(session)


def repositorio_eventos(session: SesionDB) -> RepositorioEventos:
    return RepositorioEventos(session)


def repositorio_ponentes(session: SesionDB) -> RepositorioPonentes:
    return RepositorioPonentes(session)


def repositorio_sesiones(session: SesionDB) -> RepositorioSesiones:
    return RepositorioSesiones(session)


ConfigApp = Annotated[Settings, Depends(get_settings)]
RepoUsuarios = Annotated[RepositorioUsuarios, Depends(repositorio_usuarios)]
RepoEventos = Annotated[RepositorioEventos, Depends(repositorio_eventos)]
RepoPonentes = Annotated[RepositorioPonentes, Depends(repositorio_ponentes)]
RepoSesiones = Annotated[RepositorioSesiones, Depends(repositorio_sesiones)]


def usuario_actual(
    request: Request,
    repo: RepoUsuarios,
    settings: ConfigApp,
    token: Annotated[str | None, Depends(esquema_bearer)],
) -> User:
    """El único lugar que resuelve quién hace el request. Lee el usuario de la base cada vez."""
    if token is None:
        raise Unauthorized()
    usuario = autenticacion.usuario_del_token(repo, token, settings.jwt_secret)
    request.state.user_id = usuario.id  # para el log de acceso
    return usuario


UsuarioActual = Annotated[User, Depends(usuario_actual)]


def usuario_opcional(
    request: Request,
    repo: RepoUsuarios,
    settings: ConfigApp,
    token: Annotated[str | None, Depends(esquema_bearer)],
) -> User | None:
    """Para endpoints públicos: sin token, o con uno inválido, el request es anónimo (sin 401)."""
    if token is None:
        return None
    try:
        return usuario_actual(request, repo, settings, token)
    except Unauthorized:
        return None


UsuarioOpcional = Annotated[User | None, Depends(usuario_opcional)]
