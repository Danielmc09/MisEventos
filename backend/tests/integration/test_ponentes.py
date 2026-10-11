"""/speakers contra PostgreSQL. Cada test usa nombres y correos con un prefijo único."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.test_eventos import auth, id_de, usuario_con_rol

pytestmark = pytest.mark.integration


@pytest.fixture
def prefijo() -> str:
    return "sp" + uuid4().hex[:8]


@pytest.fixture
def usuarios(cliente_db, conexion, prefijo) -> dict[str, str]:
    """Token de cada usuario del test, por nombre."""
    roles = {"orga": "ORGANIZER", "otro": "ORGANIZER", "admin": "ADMIN"}
    return {
        nombre: usuario_con_rol(cliente_db, conexion, f"{prefijo}{nombre}@mail.com", rol)
        for nombre, rol in roles.items()
    }


def crear_ponente(cliente, token: str, nombre: str, email: str | None = None) -> dict:
    respuesta = cliente.post(
        "/speakers", json={"full_name": nombre, "email": email}, headers=auth(token)
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def buscar(cliente, token: str, q: str) -> list[dict]:
    respuesta = cliente.get("/speakers", params={"q": q, "page_size": 100}, headers=auth(token))
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["items"]


def test_el_email_lo_ven_el_creador_y_el_admin_y_otro_organizador_no(cliente_db, usuarios, prefijo):
    crear_ponente(cliente_db, usuarios["orga"], f"{prefijo} Ana Pérez", "ana@mail.com")

    vistas = {quien: buscar(cliente_db, token, prefijo) for quien, token in usuarios.items()}

    assert {quien: len(items) for quien, items in vistas.items()} == {
        "orga": 1,
        "otro": 1,
        "admin": 1,
    }
    assert vistas["orga"][0]["email"] == "ana@mail.com"
    assert vistas["admin"][0]["email"] == "ana@mail.com"
    assert "email" not in vistas["otro"][0]
    assert vistas["otro"][0]["full_name"] == f"{prefijo} Ana Pérez"


def test_eliminar_un_ponente_sin_sesiones_responde_204_y_lo_borra(
    cliente_db, conexion, usuarios, prefijo
):
    ponente = crear_ponente(cliente_db, usuarios["orga"], f"{prefijo} Ana Pérez")

    respuesta = cliente_db.delete(f"/speakers/{ponente['id']}", headers=auth(usuarios["orga"]))

    assert respuesta.status_code == 204
    assert (
        conexion.execute(
            text("SELECT count(*) FROM speakers WHERE id = :id"), {"id": ponente["id"]}
        ).scalar_one()
        == 0
    )


def test_eliminar_un_ponente_con_sesiones_responde_409_y_no_lo_borra(
    cliente_db, conexion, usuarios, prefijo
):
    ponente = crear_ponente(cliente_db, usuarios["orga"], f"{prefijo} Ana Pérez")
    # Las rutas de sesiones todavía no existen: la sesión y el vínculo van por SQL.
    evento = conexion.execute(
        text(
            "INSERT INTO events (name, start_at, end_at, capacity, status, organizer_id)"
            " VALUES (:nombre, '2030-01-10T08:00:00Z', '2030-01-10T20:00:00Z', 100, 'DRAFT', :orga)"
            " RETURNING id"
        ),
        {"nombre": f"{prefijo} PyCon", "orga": id_de(conexion, f"{prefijo}orga@mail.com")},
    ).scalar_one()
    sesion = conexion.execute(
        text(
            "INSERT INTO sessions (event_id, title, start_at, end_at)"
            " VALUES (:evento, 'Testing en Python', '2030-01-10T09:00:00Z', '2030-01-10T10:00:00Z')"
            " RETURNING id"
        ),
        {"evento": evento},
    ).scalar_one()
    conexion.execute(
        text("INSERT INTO session_speakers (session_id, speaker_id) VALUES (:s, :p)"),
        {"s": sesion, "p": ponente["id"]},
    )

    respuesta = cliente_db.delete(f"/speakers/{ponente['id']}", headers=auth(usuarios["admin"]))

    assert respuesta.status_code == 409
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert (
        conexion.execute(
            text("SELECT count(*) FROM speakers WHERE id = :id"), {"id": ponente["id"]}
        ).scalar_one()
        == 1
    )


def test_q_con_porcentaje_o_guion_bajo_los_busca_literalmente(cliente_db, usuarios, prefijo):
    token = usuarios["orga"]
    for nombre in ("Ana 100% Python", "Sin comodines", "con_guion"):
        crear_ponente(cliente_db, token, f"{prefijo} {nombre}")

    porcentaje = [p["full_name"] for p in buscar(cliente_db, token, "%")]
    guion = [p["full_name"] for p in buscar(cliente_db, token, "_")]

    assert f"{prefijo} Ana 100% Python" in porcentaje
    assert all("%" in nombre for nombre in porcentaje)
    assert f"{prefijo} con_guion" in guion
    assert all("_" in nombre for nombre in guion)
    assert [p["full_name"] for p in buscar(cliente_db, token, f"{prefijo} sin")] == [
        f"{prefijo} Sin comodines"
    ]
