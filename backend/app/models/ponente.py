from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, func, text
from sqlmodel import Field, SQLModel


class Speaker(SQLModel, table=True):
    """Global: el mismo ponente se reutiliza en sesiones de distintos eventos."""

    __tablename__ = "speakers"
    __table_args__ = (
        CheckConstraint("char_length(full_name) BETWEEN 2 AND 120", name="largo_nombre"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    full_name: str = Field(sa_type=String(120), nullable=False)
    bio: str | None = Field(default=None, sa_type=String(2000))
    # Dato personal: solo lo ven quien creó el ponente y el admin.
    email: str | None = Field(default=None, sa_type=String(254))
    created_by: UUID = Field(foreign_key="users.id", nullable=False)
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
