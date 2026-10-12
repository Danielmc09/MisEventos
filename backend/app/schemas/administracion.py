from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.permisos import Rol
from app.schemas.auth import Email
from app.schemas.comunes import EntradaBase, FechaUTC


class UsuarioEdicion(EntradaBase):
    """Lo que el admin le cambia a un usuario: el nombre, el email, el rol y si está activo. La
    contraseña y cualquier otro campo responden 422."""

    model_config = ConfigDict(extra="forbid")

    # Las mismas reglas que el nombre del registro.
    full_name: str | None = Field(default=None, max_length=120)
    # Validado y normalizado igual que en el registro.
    email: Email | None = None
    role: Rol | None = None
    is_active: bool | None = None

    @field_validator("email", "role", "is_active")
    @classmethod
    def no_nulo(cls, valor: object) -> object:
        # Ausente sí (no cambia); null no: los tres son obligatorios en el usuario.
        if valor is None:
            raise ValueError("No puede ser nulo")
        return valor


class UsuarioAlta(EntradaBase):
    """El usuario que crea el admin. La contraseña la genera el sistema: mandarla, o cualquier
    otro campo, responde 422."""

    model_config = ConfigDict(extra="forbid")

    # Validado y normalizado igual que en el registro.
    email: Email
    full_name: str | None = Field(default=None, max_length=120)
    role: Rol


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


class UsuarioCreado(UsuarioAdmin):
    """El usuario recién creado y su contraseña temporal: es la única vez que se ve."""

    temporary_password: str


class ContrasenaTemporal(BaseModel):
    """La contraseña temporal que se acaba de generar: es la única vez que se ve."""

    temporary_password: str


@dataclass(frozen=True)
class FiltrosUsuarios:
    """Lo que se pide al listar usuarios."""

    q: str | None = None
    rol: frozenset[Rol] = frozenset()  # vacío: todos los roles
    activo: bool | None = None
