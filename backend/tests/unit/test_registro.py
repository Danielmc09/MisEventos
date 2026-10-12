import secrets

import pytest

from app.core.contrasenas import hashear
from app.core.permisos import Rol
from app.models.usuario import User
from app.services import autenticacion
from tests.unit.dobles import RepositorioUsuariosFalso

MENSAJE = {"message": "Registro recibido. Iniciá sesión con tu correo y contraseña."}
# El email más largo que se acepta: 254 caracteres, con etiquetas de dominio válidas.
EMAIL_254 = "a" * 64 + "@" + "b" * 63 + "." + "c" * 63 + "." + "d" * 57 + ".com"
# Una contraseña de 8 caracteres, el mínimo aceptado.
VALIDO = {"email": "ana@mail.com", "password": secrets.token_urlsafe(16)[:8], "full_name": "Ana"}
# El hash del usuario que ya existe; se calcula antes de que el espía empiece a contar.
HASH_ORIGINAL = hashear(secrets.token_urlsafe(16))


@pytest.fixture
def hashes(monkeypatch) -> list[str]:
    """Espía sobre el hash de Argon2 que usa el servicio: registra cada contraseña hasheada."""
    llamadas: list[str] = []
    original = autenticacion.hashear

    def espia(contrasena: str) -> str:
        llamadas.append(contrasena)
        return original(contrasena)

    monkeypatch.setattr(autenticacion, "hashear", espia)
    return llamadas


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"password": "a" * 7}, "password"),
        ({"password": "a" * 129}, "password"),
        ({"email": "no-es-un-email"}, "email"),
        ({"email": "ana@"}, "email"),
        ({"role": "ADMIN"}, "role"),
        ({"full_name": "a" * 121}, "full_name"),
        ({"email": EMAIL_254.replace("@", "@x")}, "email"),
    ],
)
def test_un_cuerpo_invalido_responde_422_y_no_crea_nada(con_repo, cliente, cambios, campo):
    repo = con_repo(RepositorioUsuariosFalso())

    respuesta = cliente.post("/auth/register", json=VALIDO | cambios)

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert campo in {e["field"] for e in respuesta.json()["errors"]}
    assert repo.creados == []


def test_el_422_del_email_sale_en_espanol(con_repo, cliente):
    con_repo(RepositorioUsuariosFalso())

    respuesta = cliente.post("/auth/register", json=VALIDO | {"email": "no-es-un-email"})

    assert respuesta.status_code == 422
    errores = {e["field"]: e["message"] for e in respuesta.json()["errors"]}
    assert errores["email"] == "Debe ser un correo electrónico válido"


@pytest.mark.parametrize("password", ["a" * 8, "a" * 128])
def test_un_email_nuevo_crea_un_attendee_activo_con_hash_argon2id(con_repo, cliente, password):
    repo = con_repo(RepositorioUsuariosFalso())

    respuesta = cliente.post(
        "/auth/register", json={"email": " Ana@Mail.com ", "password": password}
    )

    assert respuesta.status_code == 201
    assert respuesta.json() == MENSAJE
    assert len(repo.creados) == 1
    creado = repo.creados[0]
    assert creado.email == "ana@mail.com"
    assert creado.role == Rol.ATTENDEE
    assert creado.is_active is True
    assert creado.password_hash.startswith("$argon2id$")
    assert password not in creado.password_hash


@pytest.mark.parametrize(
    ("email", "creados"),
    [("beto@mail.com", ["beto@mail.com"]), ("Ana@Mail.com ", [])],
    ids=["email-nuevo", "email-existente"],
)
def test_el_registro_calcula_el_hash_una_vez_exista_o_no_el_email(
    con_repo, cliente, hashes, email, creados
):
    # Con un email existente el hash se calcula igual y se descarta, para tardar lo mismo.
    original = User(email="ana@mail.com", password_hash=HASH_ORIGINAL, role=Rol.ATTENDEE)
    repo = con_repo(RepositorioUsuariosFalso(original))

    respuesta = cliente.post("/auth/register", json=VALIDO | {"email": email})

    assert respuesta.status_code == 201
    assert respuesta.json() == MENSAJE
    assert hashes == [VALIDO["password"]]
    assert [u.email for u in repo.creados] == creados
    assert original.password_hash == HASH_ORIGINAL


def test_si_otro_registro_gana_la_carrera_responde_el_mismo_201(con_repo, cliente):
    repo = con_repo(RepositorioUsuariosFalso(choca_al_crear=True))

    respuesta = cliente.post("/auth/register", json=VALIDO)

    assert respuesta.status_code == 201
    assert respuesta.json() == MENSAJE
    assert repo.creados == []


def test_un_email_de_254_caracteres_se_acepta(con_repo, cliente):
    assert len(EMAIL_254) == 254
    repo = con_repo(RepositorioUsuariosFalso())

    respuesta = cliente.post("/auth/register", json=VALIDO | {"email": EMAIL_254})

    assert respuesta.status_code == 201
    assert [u.email for u in repo.creados] == [EMAIL_254]
