from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum, Index, func, text
from sqlmodel import Field, SQLModel


class EstadoInscripcion(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class Registration(SQLModel, table=True):
    __tablename__ = "registrations"
    # Una inscripción activa por persona y evento, en la base: vale aunque el servicio fallara.
    # Las canceladas quedan afuera del índice, así que se puede volver a inscribir.
    __table_args__ = (
        Index(
            "uq_registrations_activa",
            "user_id",
            "event_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    event_id: UUID = Field(foreign_key="events.id", ondelete="CASCADE", nullable=False, index=True)
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
