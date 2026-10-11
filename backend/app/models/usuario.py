from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum, Index, String, func, text
from sqlmodel import Field, SQLModel

from app.core.permisos import Rol


class User(SQLModel, table=True):
    __tablename__ = "users"
    # Único sin distinguir mayúsculas, en la base: no depende de que el código normalice.
    __table_args__ = (Index("uq_users_email", text("lower(email)"), unique=True),)

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    email: str = Field(sa_type=String, nullable=False)
    full_name: str | None = Field(default=None, max_length=120)
    password_hash: str = Field(sa_type=String, nullable=False)
    role: Rol = Field(sa_column=Column(Enum(Rol, name="user_role"), nullable=False))
    is_active: bool = Field(default=True, sa_column_kwargs={"server_default": text("true")})
    must_change_password: bool = Field(
        default=False, sa_column_kwargs={"server_default": text("false")}
    )
    created_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"server_default": func.now()},
    )

    def __setattr__(self, nombre: str, valor: Any) -> None:
        # Un modelo de tabla no valida con Pydantic, y SQLModel escribe el valor dos veces
        # (SQLAlchemy y Pydantic), así que @validates se pisa. Este es el único paso común
        # al constructor y a la asignación.
        if nombre == "email" and isinstance(valor, str):
            valor = valor.strip().lower()
        super().__setattr__(nombre, valor)
