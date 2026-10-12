from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum, func, text
from sqlmodel import Field, SQLModel


class EstadoInscripcion(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class Registration(SQLModel, table=True):
    __tablename__ = "registrations"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    user_id: UUID = Field(foreign_key="users.id", nullable=False)
    event_id: UUID = Field(foreign_key="events.id", nullable=False)
    status: EstadoInscripcion = Field(
        default=EstadoInscripcion.ACTIVE,
        sa_column=Column(
            Enum(EstadoInscripcion, name="registration_status"),
            nullable=False,
            server_default=EstadoInscripcion.ACTIVE.value,
        ),
    )
    cancelled_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
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
