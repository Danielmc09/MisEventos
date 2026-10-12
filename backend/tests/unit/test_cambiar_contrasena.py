import secrets
from uuid import UUID

import jwt
import pytest

from app.core.contrasenas import hashear, verificar
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.usuario import User
from tests.unit.dobles import RepositorioUsuariosFalso

ACTUAL = secrets.token_urlsafe()
NUEVA = secrets.token_urlsafe()
HASH_ACTUAL = hashear(ACTUAL)


@pytest.fixture
def usuario() -> User:
    return User(
        email="ana@mail.com",
        password_hash=HASH_ACTUAL,
        role=Rol.ATTENDEE,
        must_change_password=True,
    )


@pytest.fixture
def token(con_repo, usuario, settings) -> str:
    con_repo(RepositorioUsuariosFalso(usuario))
    return crear_access_token(usuario.id, settings.jwt_secret, 5)


def cambiar(cliente, token: str | None, cuerpo: dict):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.patch("/auth/me/password", json=cuerpo, headers=headers)


def campos_con_error(respuesta) -> list[str]:
    return [e["field"] for e in respuesta.json().get("errors", [])]


def test_contrasena_actual_incorrecta_responde_422_en_current_password(cliente, token, usuario):
    respuesta = cambiar(
        cliente, token, {"current_password": secrets.token_urlsafe(), "new_password": NUEVA}
    )

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert campos_con_error(respuesta) == ["current_password"]
    assert respuesta.json()["errors"][0]["message"] == "La contraseña actual no es correcta"
    assert usuario.password_hash == HASH_ACTUAL
    assert usuario.must_change_password is True


def test_nueva_igual_a_la_actual_responde_422(cliente, token, usuario):
    respuesta = cambiar(cliente, token, {"current_password": ACTUAL, "new_password": ACTUAL})

    assert respuesta.status_code == 422
    assert campos_con_error(respuesta) == ["new_password"]
    assert respuesta.json()["errors"][0]["message"] == (
        "La nueva contraseña tiene que ser distinta de la actual"
    )
    assert usuario.password_hash == HASH_ACTUAL


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        ({"current_password": ACTUAL, "new_password": "a" * 7}, "new_password"),
        ({"current_password": ACTUAL, "new_password": "a" * 129}, "new_password"),
        ({"current_password": "a" * 129, "new_password": NUEVA}, "current_password"),
        ({"current_password": ACTUAL, "new_password": NUEVA, "role": "ADMIN"}, "role"),
        ({"new_password": NUEVA}, "current_password"),
    ],
    ids=["nueva-7", "nueva-129", "actual-129", "campo-extra", "sin-actual"],
)
def test_un_cuerpo_invalido_responde_422_sin_cambiar_nada(cliente, token, usuario, cuerpo, campo):
    respuesta = cambiar(cliente, token, cuerpo)

    assert respuesta.status_code == 422
    assert campos_con_error(respuesta) == [campo]
    assert usuario.password_hash == HASH_ACTUAL
    assert usuario.role == Rol.ATTENDEE


def test_sin_token_responde_401(cliente, token):
    respuesta = cambiar(cliente, None, {"current_password": ACTUAL, "new_password": NUEVA})

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_con_la_actual_correcta_guarda_la_nueva_y_devuelve_un_token(
    cliente, token, usuario, settings
):
    respuesta = cambiar(cliente, token, {"current_password": ACTUAL, "new_password": NUEVA})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expires_in"] == settings.access_token_minutes * 60
    claims = jwt.decode(cuerpo["access_token"], settings.jwt_secret, algorithms=["HS256"])
    assert claims["sub"] == str(usuario.id)
    assert usuario.password_hash.startswith("$argon2id$")
    assert verificar(usuario.password_hash, NUEVA)
    assert not verificar(usuario.password_hash, ACTUAL)
    assert usuario.must_change_password is False


class RepositorioConResetEnCurso(RepositorioUsuariosFalso):
    """Lo que ve el cambio de contraseña si un admin restableció la cuenta mientras tanto: la
    lectura sin bloqueo trae la fila vieja; la que bloquea, la que el reset ya confirmó."""

    def __init__(self, usuario: User, confirmado: User) -> None:
        super().__init__(usuario)
        self.confirmado = confirmado

    def por_id_para_escribir(self, id_: UUID) -> User | None:
        self.operaciones.append(("leer para escribir", id_))
        return self.confirmado if id_ == self.confirmado.id else None


def test_el_cambio_relee_la_fila_bloqueada_y_no_pisa_un_reset_confirmado(
    con_repo, cliente, settings
):
    """Un admin restableció la cuenta (temporal T) entre que se leyó el usuario y se cambió la
    contraseña: la actual que manda ya no es la vigente, así que 422 y T sigue valiendo."""
    actual = secrets.token_urlsafe()
    temporal = secrets.token_urlsafe()
    leido = User(email="ana@mail.com", password_hash=hashear(actual), role=Rol.ATTENDEE)
    confirmado = User(
        id=leido.id,
        email="ana@mail.com",
        password_hash=hashear(temporal),
        role=Rol.ATTENDEE,
        must_change_password=True,
    )
    repo = con_repo(RepositorioConResetEnCurso(leido, confirmado))
    token = crear_access_token(leido.id, settings.jwt_secret, 5)

    respuesta = cambiar(cliente, token, {"current_password": actual, "new_password": NUEVA})

    assert respuesta.status_code == 422, respuesta.text
    assert campos_con_error(respuesta) == ["current_password"]
    assert ("leer para escribir", leido.id) in repo.operaciones
    assert verificar(confirmado.password_hash, temporal)
    assert confirmado.must_change_password is True
