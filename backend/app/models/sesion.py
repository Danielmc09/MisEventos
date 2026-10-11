from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func, text
from sqlmodel import Field, SQLModel


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    event_id: UUID = Field(nullable=False)
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
    __tablename__ = "session_speakers"

    session_id: UUID = Field(primary_key=True)
    speaker_id: UUID = Field(primary_key=True)
    created_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"server_default": func.now()},
    )
