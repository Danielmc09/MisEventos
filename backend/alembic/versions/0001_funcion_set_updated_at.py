"""Función de trigger set_updated_at() para mantener updated_at desde la base.

Revision ID: 0001
Revises:
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Cada tabla de dominio la conecta con:
    #   CREATE TRIGGER <tabla>_set_updated_at BEFORE UPDATE ON <tabla>
    #   FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    # clock_timestamp() y no now(): now() es el inicio de la transacción, así que un UPDATE
    # dentro de la misma transacción que el INSERT dejaría updated_at igual a created_at.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := clock_timestamp();
            RETURN NEW;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
