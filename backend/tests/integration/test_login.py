import jwt
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

CLAVE = "Clave-Segura-1"


def registrar(cliente, email: str) -> None:
    respuesta = cliente.post("/auth/register", json={"email": email, "password": CLAVE})
    assert respuesta.status_code == 201


def login(cliente, username: str, password: str = CLAVE):
    return cliente.post("/auth/login", data={"username": username, "password": password})


def me(cliente, token: str):
    return cliente.get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def desactivar(conexion, email: str) -> None:
    conexion.execute(text("UPDATE users SET is_active = false WHERE email = :e"), {"e": email})


def test_credenciales_correctas_dan_un_token_de_60_minutos_sin_cookie(cliente_db):
    registrar(cliente_db, "ana@mail.com")

    respuesta = login(cliente_db, "ana@mail.com")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expires_in"] == 3600
    assert "set-cookie" not in respuesta.headers
    assert "role" not in jwt.decode(cuerpo["access_token"], options={"verify_signature": False})
    perfil = me(cliente_db, cuerpo["access_token"])
    assert perfil.status_code == 200
    assert perfil.json()["email"] == "ana@mail.com"
    assert perfil.json()["role"] == "ATTENDEE"
    assert perfil.json()["created_at"].endswith("Z")


def test_los_tres_fallos_de_login_responden_el_mismo_401(cliente_db, conexion):
    registrar(cliente_db, "ana@mail.com")
    registrar(cliente_db, "beto@mail.com")
    desactivar(conexion, "beto@mail.com")
    assert login(cliente_db, "ana@mail.com").status_code == 200

    respuestas = [
        login(cliente_db, "nadie@mail.com"),
        login(cliente_db, "ana@mail.com", "Otra-Clave-9"),
        login(cliente_db, "beto@mail.com"),
    ]

    assert [r.status_code for r in respuestas] == [401, 401, 401]
    cuerpos = [{k: v for k, v in r.json().items() if k != "trace_id"} for r in respuestas]
    assert cuerpos[0] == cuerpos[1] == cuerpos[2]


def test_un_usuario_desactivado_con_un_token_vigente_recibe_401(cliente_db, conexion):
    registrar(cliente_db, "ana@mail.com")
    token = login(cliente_db, "ana@mail.com").json()["access_token"]
    assert me(cliente_db, token).status_code == 200

    desactivar(conexion, "ana@mail.com")
    respuesta = me(cliente_db, token)

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
