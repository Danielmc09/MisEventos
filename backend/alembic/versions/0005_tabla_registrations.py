"""Tabla registrations: inscripciones de un usuario a un evento.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

estado = postgresql.ENUM("ACTIVE", "CANCELLED", name="registration_status", create_type=False)


def _fecha(nombre: str) -> sa.Column:
    return sa.Column(
        nombre, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    estado.create(op.get_bind())
    op.create_table(
        "registrations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("status", estado, server_default="ACTIVE", nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        _fecha("created_at"),
        _fecha("updated_at"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_registrations_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], name=op.f("fk_registrations_event_id_events")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registrations")),
    )


def downgrade() -> None:
    op.drop_table("registrations")
    estado.drop(op.get_bind())
