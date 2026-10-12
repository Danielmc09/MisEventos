"""Tabla session_registrations (reservas de lugar en una sesión), con el índice único parcial de
la reserva activa y el trigger de updated_at.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

estado = postgresql.ENUM(
    "ACTIVE", "CANCELLED", name="session_registration_status", create_type=False
)


def _fecha(nombre: str) -> sa.Column:
    return sa.Column(
        nombre, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    estado.create(op.get_bind())
    op.create_table(
        "session_registrations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("status", estado, server_default="ACTIVE", nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        _fecha("created_at"),
        _fecha("updated_at"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_session_registrations_user_id_users")
        ),
        # Borrar una sesión se lleva sus reservas; el servicio decide cuándo se puede.
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_session_registrations_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_registrations")),
    )
    # La última defensa: aunque el servicio fallara, no entra una segunda reserva activa de la
    # misma persona a la misma sesión. Las canceladas no cuentan: se puede volver a reservar.
    op.create_index(
        "uq_session_registrations_activa",
        "session_registrations",
        ["user_id", "session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        op.f("ix_session_registrations_session_id"), "session_registrations", ["session_id"]
    )
    op.create_index(op.f("ix_session_registrations_user_id"), "session_registrations", ["user_id"])
    op.execute(
        "CREATE TRIGGER session_registrations_set_updated_at BEFORE UPDATE"
        " ON session_registrations FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    # El trigger, los índices y las FK caen con la tabla; el tipo enum no, se borra aparte.
    op.drop_table("session_registrations")
    estado.drop(op.get_bind())
