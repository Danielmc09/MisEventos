"""Tabla users, con el email único sin distinguir mayúsculas y el trigger de updated_at.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

rol = postgresql.ENUM("ATTENDEE", "ORGANIZER", "ADMIN", name="user_role", create_type=False)


def upgrade() -> None:
    rol.create(op.get_bind())
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", rol, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("uq_users_email", "users", [sa.text("lower(email)")], unique=True)
    op.execute(
        "CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users"
        " FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    # El trigger y el índice caen con la tabla; el tipo enum no, se borra aparte.
    op.drop_table("users")
    rol.drop(op.get_bind())
