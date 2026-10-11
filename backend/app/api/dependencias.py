from typing import Annotated

from fastapi import Depends

from app.core.db import SesionDB
from app.repositories.usuarios import RepositorioUsuarios


def repositorio_usuarios(session: SesionDB) -> RepositorioUsuarios:
    return RepositorioUsuarios(session)


RepoUsuarios = Annotated[RepositorioUsuarios, Depends(repositorio_usuarios)]
