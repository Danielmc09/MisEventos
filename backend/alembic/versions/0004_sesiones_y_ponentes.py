"""Tablas sessions, speakers y session_speakers.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fechas() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "speakers",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("bio", sa.String(length=2000), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        *_fechas(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_speakers")),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("room", sa.String(length=80), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        *_fechas(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    op.create_table(
        "session_speakers",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("speaker_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    pass
