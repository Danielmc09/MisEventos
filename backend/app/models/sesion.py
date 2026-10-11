from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, func, text
from sqlmodel import Field, SQLModel


class Session(SQLModel, table=True):
    __tablename__ = "sessions"
    # Las reglas también viven en la base: valen aunque alguien escriba sin pasar por la API.
    # Un CHECK con NULL no falla, así que una capacidad nula (sin límite propio) pasa.
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="fechas_ordenadas"),
        CheckConstraint("char_length(title) BETWEEN 3 AND 150", name="largo_titulo"),
        CheckConstraint("capacity >= 1", name="capacidad"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    event_id: UUID = Field(foreign_key="events.id", ondelete="CASCADE", nullable=False, index=True)
    title: str = Field(sa_type=String(150), nullable=False)
    description: str | None = Field(default=None, sa_type=String(2000))
    room: str | None = Field(default=None, sa_type=String(80))
    start_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    end_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    capacity: int | None = Field(default=None)
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


class SessionSpeaker(SQLModel, table=True):
    """El vínculo se crea o se borra, nunca se edita: no lleva updated_at."""

    __tablename__ = "session_speakers"

    session_id: UUID = Field(foreign_key="sessions.id", ondelete="CASCADE", primary_key=True)
    # RESTRICT: un ponente con sesiones no se borra, aunque el código no lo revise.
    speaker_id: UUID = Field(
        foreign_key="speakers.id", ondelete="RESTRICT", primary_key=True, index=True
    )
    created_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"server_default": func.now()},
    )
