"""Toda tabla de dominio tiene created_at, updated_at y el trigger que mantiene updated_at."""

import pytest
from sqlalchemy import Connection, text

pytestmark = pytest.mark.integration

# Tablas que no son de dominio o que la regla exceptúa a propósito.
EXCEPCIONES = {
    "alembic_version",
    # Un vínculo sesión-ponente no se edita: se crea o se borra. Tiene created_at, pero ni
    # updated_at ni trigger, porque no hay nada que actualizar.
    "session_speakers",
}


def tablas(conexion: Connection) -> set[str]:
    return set(
        conexion.execute(
            text(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        ).scalars()
    )


def columnas_de_fecha(conexion: Connection, tabla: str) -> set[str]:
    """Las columnas created_at/updated_at que son timestamptz NOT NULL con default."""
    return set(
        conexion.execute(
            text(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = 'public' AND table_name = :tabla"
                " AND column_name IN ('created_at', 'updated_at')"
                " AND data_type = 'timestamp with time zone'"
                " AND is_nullable = 'NO' AND column_default IS NOT NULL"
            ),
            {"tabla": tabla},
        ).scalars()
    )


def tiene_trigger_de_updated_at(conexion: Connection, tabla: str) -> bool:
    return conexion.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.triggers"
            " WHERE event_object_schema = 'public' AND event_object_table = :tabla"
            " AND event_manipulation = 'UPDATE' AND action_timing = 'BEFORE'"
            " AND action_orientation = 'ROW'"
            " AND action_statement = 'EXECUTE FUNCTION set_updated_at()')"
        ),
        {"tabla": tabla},
    ).scalar_one()


def test_toda_tabla_de_dominio_tiene_fechas_de_registro_y_trigger(conexion):
    de_dominio = tablas(conexion) - EXCEPCIONES
    assert de_dominio, "No hay tablas de dominio que revisar: el test no estaría probando nada"

    faltan = {
        tabla: problemas
        for tabla in sorted(de_dominio)
        if (
            problemas := [
                *sorted({"created_at", "updated_at"} - columnas_de_fecha(conexion, tabla)),
                *([] if tiene_trigger_de_updated_at(conexion, tabla) else ["trigger"]),
            ]
        )
    }
    assert faltan == {}
