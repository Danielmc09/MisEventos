"""Una contraseña rechazada en la validación no vuelve en la respuesta ni queda en los logs.
Pydantic adjunta el valor recibido (`input`) a cada error; si el 422 lo propagara, la contraseña
viajaría de vuelta al cliente y a cualquier log que registre la respuesta."""

import logging
import secrets
from collections.abc import Callable

import pytest

from app.core.contrasenas import hashear
from app.core.logs import FormatoJson
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.usuario import User
from tests.unit.dobles import RepositorioUsuariosFalso

ACTUAL = secrets.token_urlsafe()
USUARIO = User(email="ana@mail.com", password_hash=hashear(ACTUAL), role=Rol.ATTENDEE)


def login(cliente, _token: str, clave: str):
    return cliente.post("/auth/login", data={"username": USUARIO.email, "password": clave})


def registro(cliente, _token: str, clave: str):
    cuerpo = {"email": "nueva@mail.com", "password": clave, "full_name": "Nueva"}
    return cliente.post("/auth/register", json=cuerpo)


def cambio_actual(cliente, token: str, clave: str):
    cuerpo = {"current_password": clave, "new_password": secrets.token_urlsafe()}
    return cliente.patch(
        "/auth/me/password", json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )


def cambio_nueva(cliente, token: str, clave: str):
    cuerpo = {"current_password": ACTUAL, "new_password": clave}
    return cliente.patch(
        "/auth/me/password", json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )


@pytest.fixture
def token(con_repo, settings) -> str:
    con_repo(RepositorioUsuariosFalso(USUARIO))
    return crear_access_token(USUARIO.id, settings.jwt_secret, 5)


def texto_de_los_logs(caplog) -> str:
    """Todo lo que se registró: el mensaje, la línea JSON que se escribe y cada atributo."""
    formato = FormatoJson()
    return caplog.text + "".join(
        formato.format(registro) + repr(vars(registro)) for registro in caplog.records
    )


@pytest.mark.parametrize(
    ("enviar", "campo"),
    [
        (login, "password"),
        (registro, "password"),
        (cambio_actual, "current_password"),
        (cambio_nueva, "new_password"),
    ],
    ids=["login", "registro", "cambio-actual", "cambio-nueva"],
)
def test_una_contrasena_con_el_caracter_nulo_no_vuelve_ni_queda_en_los_logs(
    cliente, token, caplog, enviar: Callable, campo: str
):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="miseventos")
    clave = secrets.token_urlsafe()

    respuesta = enviar(cliente, token, clave + "\x00")

    assert respuesta.status_code == 422
    assert campo in [e["field"] for e in respuesta.json()["errors"]]
    # Sobre el texto crudo: contiene la clave sin el nulo, y también con él en cualquier escape.
    assert clave not in respuesta.text
    # El log del request sí se capturó; si no, la búsqueda de abajo no probaría nada.
    assert any(r.name == "miseventos.acceso" for r in caplog.records)
    assert clave not in texto_de_los_logs(caplog)
