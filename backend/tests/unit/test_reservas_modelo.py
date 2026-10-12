"""La tabla de reservas, tal como la describen los modelos y la migración, sin tocar la base."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlmodel import SQLModel

import app.models  # noqa: F401 - registra los modelos en la metadata

BACKEND = Path(__file__).resolve().parents[2]
TABLA = "session_registrations"


def tabla():
    assert TABLA in SQLModel.metadata.tables, "no hay modelo para las reservas"
    return SQLModel.metadata.tables[TABLA]


def test_la_reserva_tiene_sus_columnas():
    assert set(tabla().columns.keys()) == {
        "id",
        "user_id",
        "session_id",
        "status",
        "cancelled_at",
        "created_at",
        "updated_at",
    }


def test_el_estado_es_un_enum_propio_activa_o_cancelada():
    estado = tabla().columns["status"]

    assert estado.type.name == "session_registration_status"
    assert list(estado.type.enums) == ["ACTIVE", "CANCELLED"]
    assert estado.nullable is False
    assert tabla().columns["cancelled_at"].nullable is True


def test_la_reserva_cuelga_del_usuario_y_se_borra_con_la_sesion():
    fks = {fk.parent.name: fk for fk in tabla().foreign_keys}

    assert fks["user_id"].target_fullname == "users.id"
    assert fks["session_id"].target_fullname == "sessions.id"
    assert fks["session_id"].ondelete == "CASCADE"


def test_una_sola_reserva_activa_por_persona_y_sesion():
    unicos = [i for i in tabla().indexes if i.unique]

    assert len(unicos) == 1
    [indice] = unicos
    assert [c.name for c in indice.columns] == ["user_id", "session_id"]
    assert str(indice.dialect_options["postgresql"]["where"]) == "status = 'ACTIVE'"


def test_hay_indice_por_sesion_y_por_usuario():
    simples = {tuple(c.name for c in i.columns) for i in tabla().indexes if not i.unique}

    assert {("session_id",), ("user_id",)} <= simples


def test_la_migracion_de_reservas_es_la_unica_cabeza_y_sigue_a_la_de_inscripciones():
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))

    assert scripts.get_heads() == ["0006"]
    assert scripts.get_revision("0006").down_revision == "0005"
