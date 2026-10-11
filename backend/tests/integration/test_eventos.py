from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

CLAVE = "Clave-Segura-1"


def usuario_con_rol(cliente, conexion, email: str, rol: str) -> str:
    """Registra el usuario, le pone el rol por SQL y devuelve su access token."""
    registro = cliente.post("/auth/register", json={"email": email, "password": CLAVE})
    assert registro.status_code == 201
    conexion.execute(
        text("UPDATE users SET role = :rol WHERE email = :e"), {"rol": rol, "e": email}
    )
    login = cliente.post("/auth/login", data={"username": email, "password": CLAVE})
    assert login.status_code == 200
    return login.json()["access_token"]


def id_de(conexion, email: str) -> str:
    return str(
        conexion.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email}).scalar_one()
    )


def auth(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def cuerpo_valido() -> dict:
    inicio = datetime.now(UTC) + timedelta(days=30)
    return {
        "name": "PyCon Bogotá",
        "start_at": inicio.isoformat(),
        "end_at": (inicio + timedelta(hours=8)).isoformat(),
        "capacity": 100,
    }


def test_un_organizador_crea_un_evento_en_borrador_a_su_nombre(cliente_db, conexion):
    token = usuario_con_rol(cliente_db, conexion, "orga@mail.com", "ORGANIZER")

    respuesta = cliente_db.post("/events", json=cuerpo_valido(), headers=auth(token))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "DRAFT"
    assert cuerpo["organizer_id"] == id_de(conexion, "orga@mail.com")
    assert cuerpo["available_spots"] == 100
    assert cuerpo["created_at"].endswith("Z")
    fila = conexion.execute(
        text("SELECT status, organizer_id FROM events WHERE id = :id"), {"id": cuerpo["id"]}
    ).one()
    assert fila.status == "DRAFT"
    assert str(fila.organizer_id) == cuerpo["organizer_id"]


def test_un_borrador_solo_lo_ven_su_dueno_y_el_admin(cliente_db, conexion):
    dueno = usuario_con_rol(cliente_db, conexion, "orga@mail.com", "ORGANIZER")
    otro = usuario_con_rol(cliente_db, conexion, "otro@mail.com", "ORGANIZER")
    admin = usuario_con_rol(cliente_db, conexion, "admin@mail.com", "ADMIN")
    creado = cliente_db.post("/events", json=cuerpo_valido(), headers=auth(dueno))
    assert creado.status_code == 201
    url = f"/events/{creado.json()['id']}"

    respuestas = {
        "anonimo": cliente_db.get(url),
        "otro-organizador": cliente_db.get(url, headers=auth(otro)),
        "dueno": cliente_db.get(url, headers=auth(dueno)),
        "admin": cliente_db.get(url, headers=auth(admin)),
    }

    assert {quien: r.status_code for quien, r in respuestas.items()} == {
        "anonimo": 404,
        "otro-organizador": 404,
        "dueno": 200,
        "admin": 200,
    }
    assert respuestas["dueno"].json()["status"] == "DRAFT"


def test_un_anonimo_ve_un_evento_publicado(cliente_db, conexion):
    dueno = usuario_con_rol(cliente_db, conexion, "orga@mail.com", "ORGANIZER")
    creado = cliente_db.post("/events", json=cuerpo_valido(), headers=auth(dueno))
    assert creado.status_code == 201
    conexion.execute(
        text("UPDATE events SET status = 'PUBLISHED' WHERE id = :id"), {"id": creado.json()["id"]}
    )

    respuesta = cliente_db.get(f"/events/{creado.json()['id']}")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "PUBLISHED"
