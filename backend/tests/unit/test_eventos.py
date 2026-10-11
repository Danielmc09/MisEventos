from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.api.dependencias import repositorio_eventos, repositorio_usuarios
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.evento import EstadoEvento, Event
from app.models.usuario import User
from app.services import eventos as servicio_eventos
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


# --- Crear: validaciones -------------------------------------------------------------------

AHORA = datetime.now(UTC)
INICIO = AHORA + timedelta(days=30)


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"end_at": INICIO.isoformat()}, "end_at"),
        ({"end_at": (INICIO - timedelta(minutes=1)).isoformat()}, "end_at"),
        ({"start_at": (AHORA - timedelta(hours=1)).isoformat()}, "start_at"),
        ({"start_at": "2030-01-10T15:00:00", "end_at": "2030-01-10T18:00:00Z"}, "start_at"),
        ({"capacity": 0}, "capacity"),
        ({"capacity": 100_001}, "capacity"),
        ({"name": "ab"}, "name"),
        ({"name": "  ab  "}, "name"),
        ({"name": "a" * 151}, "name"),
        ({"description": "a" * 5001}, "description"),
        ({"location": "a" * 201}, "location"),
        ({"status": "PUBLISHED"}, "status"),
        ({"organizer_id": str(ADMIN.id)}, "organizer_id"),
    ],
    ids=[
        "fin-igual-inicio",
        "fin-antes-inicio",
        "inicio-pasado",
        "inicio-sin-zona",
        "capacidad-0",
        "capacidad-100001",
        "nombre-2",
        "nombre-2-con-espacios",
        "nombre-151",
        "descripcion-5001",
        "lugar-201",
        "con-status",
        "con-organizer_id",
    ],
)
def test_un_cuerpo_invalido_responde_422_en_su_campo(cliente, eventos, token, cambios, campo):
    cuerpo = cuerpo_valido(
        start_at=INICIO.isoformat(), end_at=(INICIO + timedelta(hours=8)).isoformat()
    )

    respuesta = crear(cliente, cuerpo | cambios, token(ORGANIZADOR))

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert [e["field"] for e in respuesta.json()["errors"]] == [campo]
    assert eventos.eventos == {}


def test_el_nombre_se_guarda_sin_espacios_al_inicio_ni_al_final(cliente, eventos, token):
    respuesta = crear(cliente, cuerpo_valido(name="  PyCon  "), token(ORGANIZADOR))

    assert respuesta.status_code == 201
    assert respuesta.json()["name"] == "PyCon"


# --- Ver: visibilidad ----------------------------------------------------------------------


def evento(estado: EstadoEvento, organizador: User = ORGANIZADOR) -> Event:
    inicio = datetime.now(UTC) + timedelta(days=30)
    nuevo = Event(
        name="PyCon Bogotá",
        start_at=inicio,
        end_at=inicio + timedelta(hours=8),
        capacity=100,
        status=estado,
        organizer_id=organizador.id,
    )
    nuevo.created_at = nuevo.updated_at = datetime.now(UTC)
    return nuevo


PUBLICADO, CANCELADO, BORRADOR = (
    EstadoEvento.PUBLISHED,
    EstadoEvento.CANCELLED,
    EstadoEvento.DRAFT,
)

# (quién consulta, estado, dueño del evento, ¿lo ve?): una fila por caso de la tabla de visibilidad.
VISIBILIDAD = {
    "anonimo-publicado": (None, PUBLICADO, ORGANIZADOR, True),
    "anonimo-cancelado": (None, CANCELADO, ORGANIZADOR, True),
    "anonimo-borrador": (None, BORRADOR, ORGANIZADOR, False),
    "asistente-publicado": (ASISTENTE, PUBLICADO, ORGANIZADOR, True),
    "asistente-cancelado": (ASISTENTE, CANCELADO, ORGANIZADOR, True),
    "asistente-borrador": (ASISTENTE, BORRADOR, ORGANIZADOR, False),
    # Un asistente que fue organizador: sus borradores viejos tampoco los ve.
    "asistente-borrador-propio": (ASISTENTE, BORRADOR, ASISTENTE, False),
    "organizador-publicado-ajeno": (OTRO_ORGANIZADOR, PUBLICADO, ORGANIZADOR, True),
    "organizador-cancelado-ajeno": (OTRO_ORGANIZADOR, CANCELADO, ORGANIZADOR, True),
    "organizador-borrador-propio": (ORGANIZADOR, BORRADOR, ORGANIZADOR, True),
    "organizador-borrador-ajeno": (OTRO_ORGANIZADOR, BORRADOR, ORGANIZADOR, False),
    "admin-publicado": (ADMIN, PUBLICADO, ORGANIZADOR, True),
    "admin-cancelado": (ADMIN, CANCELADO, ORGANIZADOR, True),
    "admin-borrador-ajeno": (ADMIN, BORRADOR, ORGANIZADOR, True),
}


@pytest.mark.parametrize("caso", VISIBILIDAD)
def test_quien_ve_cada_evento(caso):
    usuario, estado, dueno, lo_ve = VISIBILIDAD[caso]

    assert servicio_eventos.puede_ver(usuario, evento(estado, dueno)) is lo_ve


def ver(cliente, id_evento, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.get(f"/events/{id_evento}", headers=headers)


def test_un_anonimo_ve_un_evento_publicado(cliente, eventos):
    publicado = eventos.crear(evento(PUBLICADO))

    respuesta = ver(cliente, publicado.id)

    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == str(publicado.id)
    assert respuesta.json()["status"] == "PUBLISHED"


def test_un_borrador_que_no_puede_ver_responde_404_y_no_403(cliente, eventos, token):
    borrador = eventos.crear(evento(BORRADOR))

    for respuesta in (ver(cliente, borrador.id), ver(cliente, borrador.id, token(ASISTENTE))):
        assert respuesta.status_code == 404
        assert respuesta.headers["content-type"] == "application/problem+json"
    assert ver(cliente, borrador.id, token(ORGANIZADOR)).status_code == 200


def test_un_evento_que_no_existe_responde_404(cliente, eventos):
    assert ver(cliente, uuid4()).status_code == 404


def test_un_token_invalido_en_el_detalle_se_trata_como_anonimo(cliente, eventos, settings):
    publicado = eventos.crear(evento(PUBLICADO))
    borrador = eventos.crear(evento(BORRADOR))
    vencido = crear_access_token(ORGANIZADOR.id, settings.jwt_secret, -1)

    assert ver(cliente, publicado.id, "esto.no.es-un-jwt").status_code == 200
    assert ver(cliente, borrador.id, vencido).status_code == 404
