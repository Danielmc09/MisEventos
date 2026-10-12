"""Gestión de usuarios por el administrador."""

from dataclasses import dataclass
from uuid import UUID

from app.models.usuario import User
from app.schemas.administracion import FiltrosUsuarios, UsuarioEdicion


@dataclass(frozen=True)
class ConInscripciones:
    usuario: User
    inscripciones_activas: int


def listar(
    repo, actor: User, filtros: FiltrosUsuarios, offset: int, limite: int
) -> tuple[list[ConInscripciones], int]:
    return [], 0


def cambiar(repo, actor: User, id_usuario: UUID, datos: UsuarioEdicion) -> ConInscripciones:
    usuario = repo.por_id(id_usuario)
    return ConInscripciones(usuario, 0)
