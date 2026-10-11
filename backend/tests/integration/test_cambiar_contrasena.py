import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

ACTUAL = "Clave-Segura-1"
NUEVA = "Clave-Nueva-22"


def login(cliente, password: str):
    return cliente.post("/auth/login", data={"username": "ana@mail.com", "password": password})


def test_con_la_actual_correcta_cambia_la_contrasena_y_devuelve_un_token_nuevo(
    cliente_db, conexion
):
    registro = cliente_db.post("/auth/register", json={"email": "ana@mail.com", "password": ACTUAL})
    assert registro.status_code == 201
    conexion.execute(
        text("UPDATE users SET must_change_password = true WHERE email = :e"),
        {"e": "ana@mail.com"},
    )
    token = login(cliente_db, ACTUAL).json()["access_token"]

    respuesta = cliente_db.patch(
        "/auth/me/password",
        json={"current_password": ACTUAL, "new_password": NUEVA},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert respuesta.status_code == 200
    nuevo = respuesta.json()["access_token"]
    perfil = cliente_db.get("/auth/me", headers={"Authorization": f"Bearer {nuevo}"})
    assert perfil.status_code == 200
    assert perfil.json()["email"] == "ana@mail.com"
    assert perfil.json()["must_change_password"] is False
    assert login(cliente_db, NUEVA).status_code == 200
    assert login(cliente_db, ACTUAL).status_code == 401
    filas = conexion.execute(
        text("SELECT must_change_password, password_hash FROM users WHERE email = :e"),
        {"e": "ana@mail.com"},
    ).all()
    assert len(filas) == 1
    must_change_password, password_hash = filas[0]
    assert must_change_password is False
    assert password_hash.startswith("$argon2id$")
