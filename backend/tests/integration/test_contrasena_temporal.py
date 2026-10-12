"""Contraseñas temporales contra PostgreSQL: el admin crea un usuario o le restablece la
contraseña, la persona entra con la temporal, queda frenada hasta cambiarla, y después la
temporal ya no sirve."""

import logging
import secrets
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.test_eventos import auth, cuerpo_valido, id_de, usuario_con_rol
from tests.unit.test_contrasena_no_se_filtra import texto_de_los_logs

pytestmark = pytest.mark.integration


@pytest.fixture
def prefijo() -> str:
    return "tmp" + uuid4().hex[:8]


@pytest.fixture
def admin(cliente_db, conexion, prefijo) -> str:
    return usuario_con_rol(cliente_db, conexion, f"{prefijo}admin@mail.com", "ADMIN")


def crear(cliente, token: str, email: str, rol: str = "ORGANIZER"):
    cuerpo = {"email": email, "full_name": "Persona Nueva", "role": rol}
    return cliente.post("/admin/users", json=cuerpo, headers=auth(token))


def restablecer(cliente, token: str, id_usuario: str):
    return cliente.post(f"/admin/users/{id_usuario}/reset-password", headers=auth(token))


def login(cliente, email: str, password: str):
    return cliente.post("/auth/login", data={"username": email, "password": password})


def cambiar_contrasena(cliente, token: str, actual: str, nueva: str):
    return cliente.patch(
        "/auth/me/password",
        json={"current_password": actual, "new_password": nueva},
        headers=auth(token),
    )


def fila(conexion, email: str):
    return conexion.execute(
        text("SELECT * FROM users WHERE lower(email) = lower(:e)"), {"e": email}
    ).one()


# --- Crear -------------------------------------------------------------------------------------


def test_el_admin_crea_un_usuario_con_la_temporal_solo_como_hash_argon2(
    cliente_db, conexion, admin, prefijo
):
    email = f"{prefijo}nueva@mail.com"

    respuesta = crear(cliente_db, admin, f"  {email.upper()} ")

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    cuerpo = respuesta.json()
    temporal = cuerpo["temporary_password"]
    assert len(temporal) == 16
    assert cuerpo["email"] == email
    assert cuerpo["must_change_password"] is True

    usuario = fila(conexion, email)
    assert usuario.email == email
    assert usuario.role == "ORGANIZER"
    assert usuario.must_change_password is True
    assert usuario.password_hash.startswith("$argon2id$")
    # La temporal en claro no está en ninguna columna del usuario.
    assert all(temporal not in str(valor) for valor in usuario)


def test_con_la_temporal_entra_queda_frenado_y_despues_de_cambiarla_navega_normal(
    cliente_db, conexion, admin, prefijo
):
    email = f"{prefijo}orga@mail.com"
    temporal = crear(cliente_db, admin, email).json()["temporary_password"]
    nueva = secrets.token_urlsafe()

    entrada = login(cliente_db, email, temporal)
    assert entrada.status_code == 200, entrada.text
    token = entrada.json()["access_token"]

    perfil = cliente_db.get("/auth/me", headers=auth(token))
    assert perfil.status_code == 200, perfil.text
    assert perfil.json()["must_change_password"] is True
    frenadas = [
        cliente_db.get("/me/registrations", headers=auth(token)),
        cliente_db.post("/events", json=cuerpo_valido(), headers=auth(token)),
        cliente_db.get("/events", headers=auth(token)),
    ]
    for respuesta in frenadas:
        assert respuesta.status_code == 403, respuesta.text
        assert respuesta.json()["type"] == "password-change-required"
    assert fila(conexion, email).must_change_password is True

    cambio = cambiar_contrasena(cliente_db, token, temporal, nueva)
    assert cambio.status_code == 200, cambio.text
    token = cambio.json()["access_token"]

    assert fila(conexion, email).must_change_password is False
    assert cliente_db.get("/me/registrations", headers=auth(token)).status_code == 200
    creado = cliente_db.post("/events", json=cuerpo_valido(), headers=auth(token))
    assert creado.status_code == 201, creado.text


def test_despues_de_cambiarla_la_temporal_ya_no_sirve_para_el_login(
    cliente_db, conexion, admin, prefijo
):
    email = f"{prefijo}ana@mail.com"
    temporal = crear(cliente_db, admin, email, "ATTENDEE").json()["temporary_password"]
    nueva = secrets.token_urlsafe()
    token = login(cliente_db, email, temporal).json()["access_token"]

    assert cambiar_contrasena(cliente_db, token, temporal, nueva).status_code == 200

    assert login(cliente_db, email, temporal).status_code == 401
    assert login(cliente_db, email, nueva).status_code == 200


def test_crear_con_un_email_ya_registrado_con_otras_mayusculas_es_409_email_taken(
    cliente_db, conexion, admin, prefijo
):
    email = f"{prefijo}repetido@mail.com"
    assert crear(cliente_db, admin, email).status_code == 201
    hash_original = fila(conexion, email).password_hash

    respuesta = crear(cliente_db, admin, email.upper())

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["type"] == "email-taken"
    assert "temporary_password" not in respuesta.json()
    cantidad = conexion.execute(
        text("SELECT count(*) FROM users WHERE lower(email) = :e"), {"e": email}
    ).scalar_one()
    assert cantidad == 1
    assert fila(conexion, email).password_hash == hash_original


@pytest.mark.parametrize("rol", ["ORGANIZER", "ATTENDEE"])
def test_sin_el_permiso_crear_y_restablecer_responden_403(
    cliente_db, conexion, admin, prefijo, rol
):
    token = usuario_con_rol(cliente_db, conexion, f"{prefijo}sin.permiso@mail.com", rol)
    id_admin = id_de(conexion, f"{prefijo}admin@mail.com")

    alta = crear(cliente_db, token, f"{prefijo}otra@mail.com")
    reset = restablecer(cliente_db, token, id_admin)

    assert (alta.status_code, reset.status_code) == (403, 403)
    assert fila_existe(conexion, f"{prefijo}otra@mail.com") is False


def fila_existe(conexion, email: str) -> bool:
    return conexion.execute(
        text("SELECT exists(SELECT 1 FROM users WHERE lower(email) = :e)"), {"e": email}
    ).scalar_one()


# --- Restablecer -------------------------------------------------------------------------------


def test_restablecer_da_una_temporal_nueva_y_la_anterior_deja_de_servir(
    cliente_db, conexion, admin, prefijo
):
    email = f"{prefijo}olvido@mail.com"
    primera = crear(cliente_db, admin, email, "ATTENDEE").json()["temporary_password"]
    definitiva = secrets.token_urlsafe()
    token = login(cliente_db, email, primera).json()["access_token"]
    assert cambiar_contrasena(cliente_db, token, primera, definitiva).status_code == 200

    respuesta = restablecer(cliente_db, admin, id_de(conexion, email))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    temporal = respuesta.json()["temporary_password"]
    assert temporal not in (primera, definitiva)
    usuario = fila(conexion, email)
    assert usuario.must_change_password is True
    assert usuario.password_hash.startswith("$argon2id$")
    assert login(cliente_db, email, definitiva).status_code == 401
    entrada = login(cliente_db, email, temporal)
    assert entrada.status_code == 200
    # El token de la contraseña anterior también queda frenado hasta el cambio.
    frenado = cliente_db.get("/me/registrations", headers=auth(token))
    assert frenado.status_code == 403
    assert frenado.json()["type"] == "password-change-required"


def test_el_admin_no_se_restablece_su_propia_contrasena(cliente_db, conexion, admin, prefijo):
    email = f"{prefijo}admin@mail.com"
    hash_antes = fila(conexion, email).password_hash

    respuesta = restablecer(cliente_db, admin, id_de(conexion, email))

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["type"] == "cannot-modify-self"
    assert fila(conexion, email).password_hash == hash_antes


def test_a_un_usuario_desactivado_no_se_le_restablece_la_contrasena(
    cliente_db, conexion, admin, prefijo
):
    email = f"{prefijo}baja@mail.com"
    assert crear(cliente_db, admin, email, "ATTENDEE").status_code == 201
    id_usuario = id_de(conexion, email)
    desactivar = cliente_db.patch(
        f"/admin/users/{id_usuario}", json={"is_active": False}, headers=auth(admin)
    )
    assert desactivar.status_code == 200, desactivar.text
    hash_antes = fila(conexion, email).password_hash

    respuesta = restablecer(cliente_db, admin, id_usuario)

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["type"] == "user-inactive"
    assert fila(conexion, email).password_hash == hash_antes


def test_restablecer_a_un_usuario_inexistente_responde_404(cliente_db, admin):
    assert restablecer(cliente_db, admin, str(uuid4())).status_code == 404


# --- La temporal se ve una sola vez ----------------------------------------------------------


def test_la_temporal_no_aparece_en_ninguna_otra_respuesta(cliente_db, conexion, admin, prefijo):
    email = f"{prefijo}una.vez@mail.com"
    alta = crear(cliente_db, admin, email, "ATTENDEE")
    id_usuario = id_de(conexion, email)
    reset = restablecer(cliente_db, admin, id_usuario)
    temporales = [alta.json()["temporary_password"], reset.json()["temporary_password"]]
    token = login(cliente_db, email, temporales[1]).json()["access_token"]

    otras = [
        cliente_db.get("/admin/users", params={"q": prefijo}, headers=auth(admin)),
        cliente_db.get("/auth/me", headers=auth(token)),
        cliente_db.patch(
            f"/admin/users/{id_usuario}", json={"full_name": "Otro Nombre"}, headers=auth(admin)
        ),
    ]

    for respuesta in otras:
        assert respuesta.status_code == 200, respuesta.text
        assert "temporary_password" not in respuesta.text
        assert all(temporal not in respuesta.text for temporal in temporales)


def test_la_temporal_no_aparece_en_ningun_log(cliente_db, conexion, admin, prefijo, caplog):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="miseventos")
    email = f"{prefijo}sin.logs@mail.com"

    alta = crear(cliente_db, admin, email, "ATTENDEE")
    reset = restablecer(cliente_db, admin, id_de(conexion, email))
    temporales = [alta.json()["temporary_password"], reset.json()["temporary_password"]]
    token = login(cliente_db, email, temporales[1]).json()["access_token"]
    cambio = cambiar_contrasena(cliente_db, token, temporales[1], secrets.token_urlsafe())
    assert cambio.status_code == 200, cambio.text

    # El log de los requests sí se capturó; si no, la búsqueda de abajo no probaría nada.
    assert any(r.name == "miseventos.acceso" for r in caplog.records)
    logs = texto_de_los_logs(caplog)
    assert all(temporal not in logs for temporal in temporales)
