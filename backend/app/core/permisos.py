"""Qué puede hacer cada rol. El código nunca pregunta por el rol: pregunta por un permiso."""

from enum import StrEnum
from typing import Protocol


class Rol(StrEnum):
    ATTENDEE = "ATTENDEE"
    ORGANIZER = "ORGANIZER"
    ADMIN = "ADMIN"


class Permiso(StrEnum):
    EVENTO_CREAR = "evento:crear"
    EVENTO_GESTIONAR_TODOS = "evento:gestionar_todos"
    USUARIOS_GESTIONAR = "usuarios:gestionar"
    AUDITORIA_VER = "auditoria:ver"


class ConRol(Protocol):
    role: Rol


PERMISOS_POR_ROL: dict[Rol, frozenset[Permiso]] = {rol: frozenset() for rol in Rol}


def tiene_permiso(usuario: ConRol, permiso: Permiso) -> bool:
    return False
