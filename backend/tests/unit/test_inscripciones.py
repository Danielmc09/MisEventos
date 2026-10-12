"""Inscripciones a un evento: las reglas de inscribirse, en su orden, y cancelar la propia."""

from datetime import UTC, datetime, timedelta

import pytest

from app.api.dependencias import (
    repositorio_eventos,
    repositorio_inscripciones,
    repositorio_usuarios,
)
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import EstadoInscripcion, Registration
from app.models.usuario import User
from tests.unit.dobles import (
    RepositorioEventosFalso,
    RepositorioInscripcionesFalso,
    RepositorioUsuariosFalso,
)

ASISTENTE = User(email="asistente@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
OTRO_ASISTENTE = User(email="otro@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
ORGANIZADOR = User(email="orga@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
ADMIN = User(email="admin@mail.com", password_hash="$argon2id$x", role=Rol.ADMIN)


class Repos:
    def __init__(self) -> None:
        self.eventos = RepositorioEventosFalso()
        self.inscripciones = RepositorioInscripcionesFalso(self.eventos)

    def evento(
        self, estado: EstadoEvento = EstadoEvento.PUBLISHED, *, empezado: bool = False, **cambios
    ) -> Event:
        inicio = datetime.now(UTC) + (timedelta(hours=-1) if empezado else timedelta(days=30))
        datos = {
            "name": "PyCon Bogotá",
            "start_at": inicio,
            "end_at": inicio + timedelta(hours=8),
            "capacity": 50,
            "status": estado,
            "organizer_id": ORGANIZADOR.id,
        } | cambios
        return self.eventos.crear(Event(**datos))

    def inscribir(
        self, usuario: User, evento: Event, estado: EstadoInscripcion = EstadoInscripcion.ACTIVE
    ) -> Registration:
        return self.inscripciones.crear(
            Registration(user_id=usuario.id, event_id=evento.id, status=estado)
        )

    def de(self, usuario: User, evento: Event) -> list[Registration]:
        return [
            i
            for i in self.eventos.inscripciones.values()
            if i.user_id == usuario.id and i.event_id == evento.id
        ]


@pytest.fixture
def repos(app) -> Repos:
    nuevos = Repos()
    usuarios = RepositorioUsuariosFalso(ASISTENTE, OTRO_ASISTENTE, ORGANIZADOR, ADMIN)
    app.dependency_overrides[repositorio_usuarios] = lambda: usuarios
    app.dependency_overrides[repositorio_eventos] = lambda: nuevos.eventos
    app.dependency_overrides[repositorio_inscripciones] = lambda: nuevos.inscripciones
    return nuevos


@pytest.fixture
def auth(settings):
    def de(usuario: User | None) -> dict:
        if usuario is None:
            return {}
        return {"Authorization": f"Bearer {crear_access_token(usuario.id, settings.jwt_secret, 5)}"}

    return de


def inscribirse(cliente, evento: Event, headers: dict, **kwargs):
    return cliente.post(f"/events/{evento.id}/registrations", headers=headers, **kwargs)


def lleno(repos: Repos, evento: Event) -> None:
    """Ocupa todos los cupos con inscripciones de otras personas."""
    for _ in range(evento.capacity):
        otro = User(email="x@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
        repos.inscribir(otro, evento)


def assert_conflicto(respuesta, tipo: str) -> None:
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo["type"] == tipo
    assert cuerpo["title"]
    assert cuerpo["trace_id"]


# --- Inscribirse ---------------------------------------------------------------------------


def test_inscribirse_a_un_evento_publicado_con_cupo_responde_201(cliente, repos, auth):
    evento = repos.evento()

    respuesta = inscribirse(cliente, evento, auth(ASISTENTE))

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "event_id", "status", "created_at"}
    assert cuerpo["event_id"] == str(evento.id)
    assert cuerpo["status"] == "ACTIVE"
    assert cuerpo["created_at"].endswith("Z")
    [guardada] = repos.de(ASISTENTE, evento)
    assert str(guardada.id) == cuerpo["id"]
    assert guardada.status == EstadoInscripcion.ACTIVE


def test_inscribirse_bloquea_la_fila_del_evento(cliente, repos, auth):
    evento = repos.evento()

    inscribirse(cliente, evento, auth(ASISTENTE))

    assert repos.eventos.bloqueos == [evento.id]


def test_un_borrador_lleno_responde_event_not_open_y_no_capacity_full(cliente, repos, auth):
    # El dueño ve su borrador, así que no corta en 404: llega a las reglas de estado y cupo.
    borrador = repos.evento(EstadoEvento.DRAFT, capacity=2)
    lleno(repos, borrador)

    respuesta = inscribirse(cliente, borrador, auth(ORGANIZADOR))

    assert_conflicto(respuesta, "event-not-open")
    assert repos.de(ORGANIZADOR, borrador) == []


def test_un_evento_cancelado_responde_event_not_open(cliente, repos, auth):
    evento = repos.evento(EstadoEvento.CANCELLED)

    assert_conflicto(inscribirse(cliente, evento, auth(ASISTENTE)), "event-not-open")


def test_un_evento_que_ya_empezo_responde_event_started_aunque_este_lleno(cliente, repos, auth):
    evento = repos.evento(empezado=True, capacity=1)
    lleno(repos, evento)

    assert_conflicto(inscribirse(cliente, evento, auth(ASISTENTE)), "event-started")


def test_inscribirse_dos_veces_responde_already_registered_aunque_este_lleno(cliente, repos, auth):
    evento = repos.evento(capacity=1)
    repos.inscribir(ASISTENTE, evento)

    respuesta = inscribirse(cliente, evento, auth(ASISTENTE))

    assert_conflicto(respuesta, "already-registered")
    assert len(repos.de(ASISTENTE, evento)) == 1


def test_un_evento_lleno_responde_capacity_full_con_la_capacidad_en_el_detalle(
    cliente, repos, auth
):
    evento = repos.evento(capacity=3)
    lleno(repos, evento)

    respuesta = inscribirse(cliente, evento, auth(ASISTENTE))

    assert_conflicto(respuesta, "capacity-full")
    assert respuesta.json()["title"] == "El evento no tiene cupos"
    assert "3" in respuesta.json()["detail"]
    assert repos.de(ASISTENTE, evento) == []


def test_las_canceladas_no_ocupan_cupo(cliente, repos, auth):
    evento = repos.evento(capacity=1)
    repos.inscribir(OTRO_ASISTENTE, evento, EstadoInscripcion.CANCELLED)

    assert inscribirse(cliente, evento, auth(ASISTENTE)).status_code == 201


def test_el_ultimo_cupo_entra(cliente, repos, auth):
    evento = repos.evento(capacity=2)
    repos.inscribir(OTRO_ASISTENTE, evento)

    assert inscribirse(cliente, evento, auth(ASISTENTE)).status_code == 201


def test_un_borrador_ajeno_responde_404(cliente, repos, auth):
    borrador = repos.evento(EstadoEvento.DRAFT)

    respuesta = inscribirse(cliente, borrador, auth(ASISTENTE))

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "not-found"


def test_un_evento_que_no_existe_responde_404(cliente, repos, auth):
    fantasma = Event(
        name="No existe",
        start_at=datetime.now(UTC),
        end_at=datetime.now(UTC),
        capacity=1,
        organizer_id=ORGANIZADOR.id,
    )

    assert inscribirse(cliente, fantasma, auth(ASISTENTE)).status_code == 404


def test_sin_token_responde_401(cliente, repos):
    evento = repos.evento()

    respuesta = inscribirse(cliente, evento, {})

    assert respuesta.status_code == 401
    assert repos.eventos.inscripciones == {}


def test_un_campo_desconocido_en_el_cuerpo_responde_422(cliente, repos, auth):
    evento = repos.evento()

    respuesta = inscribirse(cliente, evento, auth(ASISTENTE), json={"confirm_overlap": True})

    assert respuesta.status_code == 422
    assert respuesta.json()["errors"][0]["field"] == "confirm_overlap"
    assert repos.eventos.inscripciones == {}


def test_un_cuerpo_vacio_se_acepta(cliente, repos, auth):
    evento = repos.evento()

    assert inscribirse(cliente, evento, auth(ASISTENTE), json={}).status_code == 201
