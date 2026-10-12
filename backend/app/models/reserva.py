from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum, Index, func, text
from sqlmodel import Field, SQLModel


class EstadoReserva(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class SessionRegistration(SQLModel, table=True):
    """El lugar de una persona en una sesión."""

    __tablename__ = "session_registrations"
    # Una reserva activa por persona y sesión, en la base: vale aunque el servicio fallara.
    # Las canceladas quedan afuera del índice, así que se puede volver a reservar.
    __table_args__ = (
        Index(
            "uq_session_registrations_activa",
            "user_id",
            "session_id",
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
    session_id: UUID = Field(
        foreign_key="sessions.id", ondelete="CASCADE", nullable=False, index=True
    )
    status: EstadoReserva = Field(
        default=EstadoReserva.ACTIVE,
        sa_column=Column(
            Enum(EstadoReserva, name="session_registration_status"),
            nullable=False,
            server_default=EstadoReserva.ACTIVE.value,
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
