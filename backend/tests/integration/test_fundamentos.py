import pytest
from sqlalchemy import Connection, text

from tests.integration.infraestructura import migrar, revertir

pytestmark = pytest.mark.integration


def funcion_de_trigger_existe(conexion: Connection, nombre: str) -> bool:
    return conexion.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_proc p"
            " JOIN pg_namespace n ON n.oid = p.pronamespace"
            " WHERE p.proname = :nombre AND n.nspname = 'public'"
            " AND p.prorettype = 'trigger'::regtype)"
        ),
        {"nombre": nombre},
    ).scalar_one()


def test_health_responde_200_con_la_base_arriba(cliente_db):
    respuesta = cliente_db.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_la_migracion_deja_la_funcion_set_updated_at(conexion):
    assert funcion_de_trigger_existe(conexion, "set_updated_at")


def test_set_updated_at_cambia_updated_at_y_no_created_at(conexion):
    # Tabla temporal, no de dominio: prueba la función en sí, dentro de la transacción del test.
    conexion.execute(
        text(
            "CREATE TEMP TABLE prueba_trigger ("
            " id int PRIMARY KEY, nombre text NOT NULL,"
            " created_at timestamptz NOT NULL DEFAULT now(),"
            " updated_at timestamptz NOT NULL DEFAULT now())"
        )
    )
    conexion.execute(
        text(
            "CREATE TRIGGER prueba_trigger_set_updated_at BEFORE UPDATE ON prueba_trigger"
            " FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )
    )
    conexion.execute(text("INSERT INTO prueba_trigger (id, nombre) VALUES (1, 'antes')"))
    antes = conexion.execute(text("SELECT created_at, updated_at FROM prueba_trigger")).one()

    conexion.execute(text("UPDATE prueba_trigger SET nombre = 'después' WHERE id = 1"))

    despues = conexion.execute(text("SELECT created_at, updated_at FROM prueba_trigger")).one()
    assert despues.created_at == antes.created_at
    assert despues.updated_at > antes.updated_at


def test_downgrade_base_y_upgrade_head_funcionan(conexion):
    revertir(conexion, "base")
    assert not funcion_de_trigger_existe(conexion, "set_updated_at")

    migrar(conexion, "head")
    assert funcion_de_trigger_existe(conexion, "set_updated_at")
