from dataclasses import dataclass

from app.core.permisos import Rol
from app.schemas.comunes import EntradaBase


class UsuarioEdicion(EntradaBase):
    role: Rol | None = None
    is_active: bool | None = None


@dataclass(frozen=True)
class FiltrosUsuarios:
    q: str | None = None
    rol: Rol | None = None
    activo: bool | None = None
