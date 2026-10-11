"""Tablas sessions, speakers y session_speakers, con sus reglas, índices y triggers de updated_at.

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


def _fecha(nombre: str) -> sa.Column:
    return sa.Column(
        nombre, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "speakers",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("bio", sa.String(length=2000), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _fecha("created_at"),
        _fecha("updated_at"),
        sa.CheckConstraint(
            "char_length(full_name) BETWEEN 2 AND 120", name=op.f("ck_speakers_largo_nombre")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_speakers_created_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_speakers")),
    )
    op.execute(
        "CREATE TRIGGER speakers_set_updated_at BEFORE UPDATE ON speakers"
        " FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
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
        _fecha("created_at"),
        _fecha("updated_at"),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_sessions_fechas_ordenadas")),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 3 AND 150", name=op.f("ck_sessions_largo_titulo")
        ),
        # Con NULL el CHECK no falla: una sesión sin capacidad propia usa la del evento.
        sa.CheckConstraint("capacity >= 1", name=op.f("ck_sessions_capacidad")),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_sessions_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    op.create_index(op.f("ix_sessions_event_id"), "sessions", ["event_id"])
    op.execute(
        "CREATE TRIGGER sessions_set_updated_at BEFORE UPDATE ON sessions"
        " FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # Sin updated_at ni trigger: el vínculo se crea o se borra, nunca se edita.
    op.create_table(
        "session_speakers",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("speaker_id", sa.Uuid(), nullable=False),
        _fecha("created_at"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_session_speakers_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["speaker_id"],
            ["speakers.id"],
            name=op.f("fk_session_speakers_speaker_id_speakers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("session_id", "speaker_id", name=op.f("pk_session_speakers")),
    )
    # La PK ya indexa por session_id primero; para buscar por ponente hace falta este.
    op.create_index(op.f("ix_session_speakers_speaker_id"), "session_speakers", ["speaker_id"])


def downgrade() -> None:
    # Triggers, índices, CHECK y FK caen con cada tabla. Primero la que referencia a las otras.
    op.drop_table("session_speakers")
    op.drop_table("sessions")
    op.drop_table("speakers")
