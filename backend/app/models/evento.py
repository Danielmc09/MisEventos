from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum, String, func, text
from sqlmodel import Field, SQLModel


class EstadoEvento(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    name: str = Field(sa_type=String(150), nullable=False)
    description: str | None = Field(default=None, sa_type=String(5000))
    location: str | None = Field(default=None, sa_type=String(200))
    start_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False, index=True)
    end_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    capacity: int = Field(nullable=False)
    status: EstadoEvento = Field(
        default=EstadoEvento.DRAFT,
        sa_column=Column(Enum(EstadoEvento, name="event_status"), nullable=False),
    )
    organizer_id: UUID = Field(foreign_key="users.id", nullable=False)
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
