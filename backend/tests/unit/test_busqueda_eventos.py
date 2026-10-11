from datetime import UTC, datetime, timedelta

import pytest

from app.api.dependencias import repositorio_eventos, repositorio_usuarios
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.evento import EstadoEvento, Event
from app.models.usuario import User
from app.repositories.eventos import escapar_like
from tests.unit.dobles import RepositorioEventosFalso, RepositorioUsuariosFalso

ASISTENTE = User(email="asistente@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
ORGANIZADOR = User(email="orga@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
ADMIN = User(email="admin@mail.com", password_hash="$argon2id$x", role=Rol.ADMIN)


def evento(nombre: str) -> Event:
    inicio = datetime.now(UTC) + timedelta(days=10)
    ahora = datetime.now(UTC)
    return Event(
        name=nombre,
        start_at=inicio,
        end_at=inicio + timedelta(hours=2),
        capacity=50,
        status=EstadoEvento.PUBLISHED,
        organizer_id=ORGANIZADOR.id,
        created_at=ahora,
        updated_at=ahora,
    )


@pytest.fixture
def repo(app) -> RepositorioEventosFalso:
    eventos = RepositorioEventosFalso(evento("Uno"), evento("Dos"), evento("Tres"))
    usuarios = RepositorioUsuariosFalso(ASISTENTE, ORGANIZADOR, ADMIN)
    app.dependency_overrides[repositorio_usuarios] = lambda: usuarios
    app.dependency_overrides[repositorio_eventos] = lambda: eventos
    return eventos


def listar(cliente, settings, params=None, usuario: User | None = None):
    headers = {}
    if usuario is not None:
        token = crear_access_token(usuario.id, settings.jwt_secret, 5)
        headers["Authorization"] = f"Bearer {token}"
    return cliente.get("/events", params=params, headers=headers)


@pytest.mark.parametrize(
    ("texto", "escapado"),
    [
        ("100%", "100\\%"),
        ("mi_evento", "mi\\_evento"),
        ("a\\b", "a\\\\b"),
        ("%_\\", "\\%\\_\\\\"),
        ("' OR 1=1 --", "' OR 1=1 --"),
        ("PyCon Bogotá", "PyCon Bogotá"),
    ],
)
def test_el_escape_vuelve_literales_los_comodines_y_la_barra(texto, escapado):
    assert escapar_like(texto) == escapado


# --- GET /events: parámetros ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "campo"),
    [
        ({"q": "x" * 101}, "q"),
        ({"order_by": "fecha"}, "order_by"),
        ({"when": "manana"}, "when"),
        ({"status": "ARCHIVED"}, "status"),
        ({"from": "2026-10-13T10:00:00"}, "from"),
        ({"to": "2026-10-13T10:00:00"}, "to"),
    ],
)
def test_un_parametro_invalido_responde_422_en_su_campo(cliente, settings, repo, params, campo):
    respuesta = listar(cliente, settings, params)

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert [e["field"].split(".")[0] for e in respuesta.json()["errors"]] == [campo]
    assert repo.busquedas == []


def test_los_parametros_llegan_a_la_busqueda(cliente, settings, repo):
    params = {
        "q": "p" * 100,
        "status": ["PUBLISHED", "CANCELLED"],
        "from": "2026-10-13T10:00:00-05:00",
        "to": "2026-10-20T10:00:00Z",
        "when": "past",
        "order_by": "-start_at",
        "page": 3,
        "page_size": 5,
    }

    respuesta = listar(cliente, settings, params)

    assert respuesta.status_code == 200
    assert len(repo.busquedas) == 1
    [busqueda] = repo.busquedas
    filtros = busqueda["filtros"]
    assert filtros.q == "p" * 100
    assert filtros.estados == [EstadoEvento.PUBLISHED, EstadoEvento.CANCELLED]
    assert filtros.desde == datetime(2026, 10, 13, 15, tzinfo=UTC)
    assert filtros.hasta == datetime(2026, 10, 20, 10, tzinfo=UTC)
    assert filtros.cuando == "past"
    assert filtros.orden == "-start_at"
    assert (busqueda["offset"], busqueda["limite"]) == (10, 5)


def test_sin_parametros_busca_los_proximos_por_fecha_de_inicio(cliente, settings, repo):
    respuesta = listar(cliente, settings)

    assert respuesta.status_code == 200
    assert len(repo.busquedas) == 1
    [busqueda] = repo.busquedas
    filtros = busqueda["filtros"]
    assert (filtros.q, filtros.estados, filtros.desde, filtros.hasta) == (None, None, None, None)
    assert (filtros.cuando, filtros.orden) == ("upcoming", "start_at")
    assert (busqueda["offset"], busqueda["limite"]) == (0, 12)


def test_responde_la_pagina_con_total_y_paginas(cliente, settings, repo):
    respuesta = listar(cliente, settings, {"page": 2, "page_size": 2})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["total"], cuerpo["pages"], cuerpo["page"], cuerpo["page_size"]) == (3, 2, 2, 2)
    assert [e["name"] for e in cuerpo["items"]] == ["Tres"]
    assert cuerpo["items"][0]["available_spots"] == 50


# --- GET /events: visibilidad --------------------------------------------------------------


@pytest.mark.parametrize(
    ("usuario", "ver_todo", "borradores_de"),
    [
        (None, False, None),
        (ASISTENTE, False, None),
        (ORGANIZADOR, False, ORGANIZADOR.id),
        (ADMIN, True, None),
    ],
    ids=["anonimo", "asistente", "organizador", "admin"],
)
def test_la_busqueda_se_recorta_a_lo_que_el_usuario_puede_ver(
    cliente, settings, repo, usuario, ver_todo, borradores_de
):
    respuesta = listar(cliente, settings, {"status": "DRAFT"}, usuario)

    assert respuesta.status_code == 200
    assert len(repo.busquedas) == 1
    [busqueda] = repo.busquedas
    assert (busqueda["ver_todo"], busqueda["borradores_de"]) == (ver_todo, borradores_de)
