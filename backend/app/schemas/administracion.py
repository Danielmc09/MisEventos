from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.permisos import Rol
from app.schemas.comunes import EntradaBase, FechaUTC


class UsuarioEdicion(EntradaBase):
    """Lo que el admin le cambia a otro usuario: el rol y si está activo. Nada más: el nombre,
    el email o la contraseña (y cualquier otro campo) responden 422."""

    model_config = ConfigDict(extra="forbid")

    role: Rol | None = None
    is_active: bool | None = None

    @field_validator("role", "is_active")
    @classmethod
    def no_nulo(cls, valor: object) -> object:
        # Ausente sí (no cambia); null no: los dos son obligatorios en el usuario.
        if valor is None:
            raise ValueError("No puede ser nulo")
        return valor


class UsuarioAdmin(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: Rol
    is_active: bool
    must_change_password: bool
    created_at: FechaUTC
    updated_at: FechaUTC
    active_registrations: int


@dataclass(frozen=True)
class FiltrosUsuarios:
    """Lo que se pide al listar usuarios."""

    q: str | None = None
    rol: Rol | None = None
    activo: bool | None = None
