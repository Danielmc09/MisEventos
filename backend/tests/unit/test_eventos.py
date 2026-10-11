from datetime import UTC, datetime, timedelta

import pytest

from app.api.dependencias import repositorio_eventos, repositorio_usuarios
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.usuario import User
from tests.unit.dobles import RepositorioEventosFalso, RepositorioUsuariosFalso

ASISTENTE = User(email="asistente@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
ORGANIZADOR = User(email="orga@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
OTRO_ORGANIZADOR = User(email="otro@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
ADMIN = User(email="admin@mail.com", password_hash="$argon2id$x", role=Rol.ADMIN)


@pytest.fixture
def eventos(app) -> RepositorioEventosFalso:
    repo = RepositorioEventosFalso()
    usuarios = RepositorioUsuariosFalso(ASISTENTE, ORGANIZADOR, OTRO_ORGANIZADOR, ADMIN)
    app.dependency_overrides[repositorio_usuarios] = lambda: usuarios
    app.dependency_overrides[repositorio_eventos] = lambda: repo
    return repo


@pytest.fixture
def token(settings):
    def de(usuario: User) -> str:
        return crear_access_token(usuario.id, settings.jwt_secret, 5)

    return de


def cuerpo_valido(**cambios) -> dict:
    inicio = datetime.now(UTC) + timedelta(days=30)
    datos = {
        "name": "PyCon Bogotá",
        "description": "Charlas de Python",
        "location": "Bogotá",
        "start_at": inicio.isoformat(),
        "end_at": (inicio + timedelta(hours=8)).isoformat(),
        "capacity": 100,
    }
    return datos | cambios


def crear(cliente, cuerpo: dict, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.post("/events", json=cuerpo, headers=headers)


# --- Crear: permisos -----------------------------------------------------------------------


def test_un_asistente_no_puede_crear_un_evento(cliente, eventos, token):
    respuesta = crear(cliente, cuerpo_valido(), token(ASISTENTE))

    assert respuesta.status_code == 403
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert eventos.eventos == {}


def test_sin_token_no_se_puede_crear_un_evento(cliente, eventos):
    respuesta = crear(cliente, cuerpo_valido())

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
    assert eventos.eventos == {}


@pytest.mark.parametrize("usuario", [ORGANIZADOR, ADMIN], ids=["organizador", "admin"])
def test_quien_tiene_el_permiso_crea_un_borrador_a_su_nombre(cliente, eventos, token, usuario):
    respuesta = crear(cliente, cuerpo_valido(capacity=40), token(usuario))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "DRAFT"
    assert cuerpo["organizer_id"] == str(usuario.id)
    assert cuerpo["name"] == "PyCon Bogotá"
    assert cuerpo["registered_count"] == 0
    assert cuerpo["available_spots"] == 40
    assert cuerpo["is_finished"] is False
    assert cuerpo["start_at"].endswith("Z")
    assert len(eventos.eventos) == 1
