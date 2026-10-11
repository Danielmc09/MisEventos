from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app.core.config import Settings
from app.core.db import SesionDB
from app.core.excepciones import Unauthorized
from app.models.usuario import User
from app.repositories.usuarios import RepositorioUsuarios
from app.services import autenticacion

# auto_error=False: la falta de token la responde el handler de dominio, como cualquier 401.
esquema_bearer = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def repositorio_usuarios(session: SesionDB) -> RepositorioUsuarios:
    return RepositorioUsuarios(session)


ConfigApp = Annotated[Settings, Depends(get_settings)]
RepoUsuarios = Annotated[RepositorioUsuarios, Depends(repositorio_usuarios)]


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
