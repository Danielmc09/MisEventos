"""Ponentes: globales, los buscan y crean los organizadores; los edita quien los creó o el admin.

Lanza excepciones de dominio; no sabe nada de HTTP."""

from typing import Protocol
from uuid import UUID

from app.core.excepciones import Conflict, Forbidden, NotFound
from app.core.permisos import Permiso, tiene_permiso
from app.models.ponente import Speaker
from app.models.usuario import User
from app.schemas.ponentes import PonenteEdicion, PonenteEntrada


class Ponentes(Protocol):
    def buscar(self, q: str | None, offset: int, limite: int) -> tuple[list[Speaker], int]: ...
    def por_id_para_escribir(self, id_ponente: UUID) -> Speaker | None: ...
    def tiene_sesiones(self, id_ponente: UUID) -> bool: ...
    def crear(self, ponente: Speaker) -> Speaker: ...
    def guardar(self, ponente: Speaker) -> Speaker: ...
    def eliminar(self, ponente: Speaker) -> None: ...


def puede_gestionar(usuario: User, ponente: Speaker) -> bool:
    """Editar, eliminar y ver el email: quien lo creó (si sigue pudiendo gestionar ponentes)
    o el admin."""
    if tiene_permiso(usuario, Permiso.PONENTE_GESTIONAR_TODOS):
        return True
    return tiene_permiso(usuario, Permiso.PONENTE_GESTIONAR) and ponente.created_by == usuario.id


def _exigir_permiso(usuario: User) -> None:
    if not tiene_permiso(usuario, Permiso.PONENTE_GESTIONAR):
        raise Forbidden()


def buscar(
    repo: Ponentes, usuario: User, q: str | None, offset: int, limite: int
) -> tuple[list[Speaker], int]:
    _exigir_permiso(usuario)
    return repo.buscar(q, offset, limite)


def crear(repo: Ponentes, usuario: User, datos: PonenteEntrada) -> Speaker:
    _exigir_permiso(usuario)
    return repo.crear(Speaker(**datos.model_dump(), created_by=usuario.id))


def _para_escribir(repo: Ponentes, usuario: User, id_ponente: UUID) -> Speaker:
    """El ponente bloqueado. Sin el permiso general, 403 antes de revelar si existe."""
    _exigir_permiso(usuario)
    ponente = repo.por_id_para_escribir(id_ponente)
    if ponente is None:
        raise NotFound()
    if not puede_gestionar(usuario, ponente):
        raise Forbidden()
    return ponente


def editar(repo: Ponentes, usuario: User, id_ponente: UUID, datos: PonenteEdicion) -> Speaker:
    ponente = _para_escribir(repo, usuario, id_ponente)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(ponente, campo, valor)
    return repo.guardar(ponente)


def eliminar(repo: Ponentes, usuario: User, id_ponente: UUID) -> None:
    ponente = _para_escribir(repo, usuario, id_ponente)
    if repo.tiene_sesiones(ponente.id):
        raise Conflict(
            "Quitalo de sus sesiones antes de eliminarlo",
            tipo="speaker-has-sessions",
            titulo="El ponente tiene sesiones asignadas",
        )
    repo.eliminar(ponente)
