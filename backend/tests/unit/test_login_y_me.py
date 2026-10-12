import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest

from app.core.contrasenas import hashear
from app.core.excepciones import Unauthorized
from app.core.permisos import PERMISOS_POR_ROL, Permiso, Rol
from app.models.usuario import User
from app.schemas.auth import UsuarioSalida
from app.services import autenticacion
from tests.unit.dobles import RepositorioUsuariosFalso

CLAVE = "Clave-Segura-1"
HASH_CLAVE = hashear(CLAVE)


def nuevo_usuario(**cambios) -> User:
    datos = {"email": "ana@mail.com", "password_hash": HASH_CLAVE, "role": Rol.ATTENDEE}
    usuario = User(**(datos | cambios))
    usuario.created_at = datetime(2026, 10, 11, 15, 30, tzinfo=UTC)
    return usuario


@pytest.fixture
def usuario() -> User:
    return nuevo_usuario()


@pytest.fixture
def repo(con_repo, usuario) -> RepositorioUsuariosFalso:
    return con_repo(RepositorioUsuariosFalso(usuario))


def login(cliente, username: str, password: str):
    return cliente.post("/auth/login", data={"username": username, "password": password})


def sin_trace_id(respuesta) -> dict:
    return {k: v for k, v in respuesta.json().items() if k != "trace_id"}


def firmar(sub: str, secreto: str, vence_en: timedelta = timedelta(minutes=5)) -> str:
    ahora = datetime.now(UTC)
    return jwt.encode(
        {"sub": sub, "iat": ahora, "exp": ahora + vence_en}, secreto, algorithm="HS256"
    )


def sin_firma(sub: str) -> str:
    """Un token con `alg: none`: header y payload válidos, firma vacía."""

    def parte(datos: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(datos).encode()).rstrip(b"=").decode()

    exp = int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())
    return f"{parte({'alg': 'none', 'typ': 'JWT'})}.{parte({'sub': sub, 'exp': exp})}."


def me(cliente, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return cliente.get("/auth/me", headers=headers)


# --- Login ---------------------------------------------------------------------------------


def test_con_un_email_inexistente_igual_verifica_contra_un_hash_ficticio(monkeypatch):
    verificaciones: list[tuple[str, str]] = []

    def espia(hash_guardado: str, contrasena: str) -> bool:
        verificaciones.append((hash_guardado, contrasena))
        return False

    monkeypatch.setattr(autenticacion, "verificar", espia)

    with pytest.raises(Unauthorized):
        autenticacion.autenticar(RepositorioUsuariosFalso(), "nadie@mail.com", CLAVE)

    assert len(verificaciones) == 1
    hash_ficticio, contrasena = verificaciones[0]
    assert hash_ficticio.startswith("$argon2id$")
    assert contrasena == CLAVE


def test_credenciales_correctas_dan_un_access_token_sin_cookie(repo, usuario, cliente, settings):
    respuesta = login(cliente, " Ana@Mail.com", CLAVE)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expires_in"] == settings.access_token_minutes * 60
    assert "set-cookie" not in respuesta.headers
    claims = jwt.decode(cuerpo["access_token"], settings.jwt_secret, algorithms=["HS256"])
    assert claims["sub"] == str(usuario.id)
    assert claims["exp"] - claims["iat"] == settings.access_token_minutes * 60
    assert "role" not in claims
    assert me(cliente, cuerpo["access_token"]).status_code == 200


@pytest.mark.parametrize(
    ("username", "password"),
    [("ana@mail.com", "a" * 129), ("a" * 243 + "@mail.com" + "a" * 3, CLAVE)],
    ids=["password-129", "username-255"],
)
def test_credenciales_demasiado_largas_dan_el_mismo_401_sin_llamar_a_argon2(
    repo, cliente, monkeypatch, username, password
):
    assert len(username) == 255 or len(password) == 129
    assert login(cliente, "ana@mail.com", CLAVE).status_code == 200
    incorrecta = login(cliente, "ana@mail.com", "Otra-Clave-9")
    verificar, hashear_espia = Mock(return_value=True), Mock()
    monkeypatch.setattr(autenticacion, "verificar", verificar)
    monkeypatch.setattr(autenticacion, "hashear", hashear_espia)

    respuesta = login(cliente, username, password)

    assert respuesta.status_code == incorrecta.status_code == 401
    assert sin_trace_id(respuesta) == sin_trace_id(incorrecta)
    verificar.assert_not_called()
    hashear_espia.assert_not_called()


# --- Endpoint protegido --------------------------------------------------------------------


def test_me_sin_token_responde_401_con_www_authenticate(repo, cliente):
    respuesta = me(cliente)

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
    assert respuesta.headers["content-type"] == "application/problem+json"


def test_me_con_un_token_valido_devuelve_el_usuario(repo, usuario, cliente, settings):
    respuesta = me(cliente, firmar(str(usuario.id), settings.jwt_secret))

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "id": str(usuario.id),
        "email": "ana@mail.com",
        "full_name": None,
        "role": "ATTENDEE",
        "is_active": True,
        "must_change_password": False,
        "created_at": "2026-10-11T15:30:00Z",
        "permisos": [],
    }


TOKENS_INVALIDOS = {
    "vencido": lambda u, s: firmar(str(u.id), s, vence_en=timedelta(seconds=-1)),
    "otro-secreto": lambda u, s: firmar(str(u.id), "otro-secreto-" + "x" * 32),
    "alg-none": lambda u, s: sin_firma(str(u.id)),
    "sin-exp": lambda u, s: jwt.encode({"sub": str(u.id)}, s, algorithm="HS256"),
    "basura": lambda u, s: "esto.no.es-un-jwt",
    "sub-no-uuid": lambda u, s: firmar("ana@mail.com", s),
    "usuario-inexistente": lambda u, s: firmar(str(uuid4()), s),
}


@pytest.mark.parametrize("caso", TOKENS_INVALIDOS)
def test_me_con_un_token_invalido_responde_401(repo, usuario, cliente, settings, caso):
    respuesta = me(cliente, TOKENS_INVALIDOS[caso](usuario, settings.jwt_secret))

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_me_de_un_usuario_desactivado_responde_401(repo, usuario, cliente, settings):
    usuario.is_active = False

    respuesta = me(cliente, firmar(str(usuario.id), settings.jwt_secret))

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


# --- Permisos en /auth/me ------------------------------------------------------------------


@pytest.mark.parametrize("rol", list(Rol))
def test_me_trae_exactamente_los_permisos_del_rol_ordenados(con_repo, cliente, settings, rol):
    usuario = nuevo_usuario(role=rol)
    con_repo(RepositorioUsuariosFalso(usuario))

    respuesta = me(cliente, firmar(str(usuario.id), settings.jwt_secret))

    assert respuesta.status_code == 200
    assert respuesta.json().get("permisos") == sorted(PERMISOS_POR_ROL[rol])


def test_me_refleja_un_permiso_que_se_agrega_al_mapa(con_repo, cliente, settings, monkeypatch):
    usuario = nuevo_usuario(role=Rol.ATTENDEE)
    con_repo(RepositorioUsuariosFalso(usuario))
    monkeypatch.setitem(
        PERMISOS_POR_ROL, Rol.ATTENDEE, frozenset({Permiso.AUDITORIA_VER, Permiso.EVENTO_CREAR})
    )

    respuesta = me(cliente, firmar(str(usuario.id), settings.jwt_secret))

    assert respuesta.json().get("permisos") == ["auditoria:ver", "evento:crear"]


def test_el_openapi_tipa_los_permisos_de_me_como_lista_del_enum(cliente):
    esquema = cliente.get("/openapi.json").json()
    ref = esquema["paths"]["/auth/me"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    salida = esquema["components"]["schemas"][ref.rsplit("/", 1)[-1]]

    assert "permisos" in salida["properties"]
    permisos = salida["properties"]["permisos"]
    assert permisos["type"] == "array"
    enum = esquema["components"]["schemas"][permisos["items"]["$ref"].rsplit("/", 1)[-1]]
    assert sorted(enum["enum"]) == sorted(p.value for p in Permiso)
    assert "permisos" in salida["required"]
    assert "permisos" not in UsuarioSalida.model_fields
