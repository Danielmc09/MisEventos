"""Registro, login y usuario actual. Lanza excepciones de dominio; no sabe nada de HTTP."""

from typing import Protocol

from app.core.contrasenas import hashear
from app.core.permisos import Rol
from app.models.usuario import User


class Usuarios(Protocol):
    def por_email(self, email: str) -> User | None: ...
    def crear(self, usuario: User) -> bool: ...


def registrar(repo: Usuarios, email: str, password: str, full_name: str | None) -> None:
    """Crea un ATTENDEE. Si el email ya existe no hace nada, y quien llama responde lo mismo."""
    if repo.por_email(email) is not None:
        return
    usuario = User(
        email=email, password_hash=hashear(password), full_name=full_name, role=Rol.ATTENDEE
    )
    repo.crear(usuario)  # si chocó con otro registro del mismo email, la respuesta es la misma
