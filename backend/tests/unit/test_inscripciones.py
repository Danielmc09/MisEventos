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
    assert cuerpo.get("detail"), "el 409 explica en el detalle qué pasó"
    assert cuerpo["detail"] != cuerpo["title"]
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


# --- Cancelar ------------------------------------------------------------------------------


def cancelar(cliente, evento: Event, headers: dict):
    return cliente.delete(f"/events/{evento.id}/registrations/me", headers=headers)


def test_cancelar_la_propia_responde_204_y_la_deja_cancelada_con_fecha(cliente, repos, auth):
    evento = repos.evento()
    inscripcion = repos.inscribir(ASISTENTE, evento)
    antes = datetime.now(UTC)

    respuesta = cancelar(cliente, evento, auth(ASISTENTE))

    assert respuesta.status_code == 204, respuesta.text
    assert respuesta.content == b""
    assert inscripcion.status == EstadoInscripcion.CANCELLED
    assert inscripcion.cancelled_at is not None
    assert inscripcion.cancelled_at >= antes
    assert repos.eventos.bloqueos == [evento.id]


def test_cancelar_libera_el_cupo(cliente, repos, auth):
    evento = repos.evento(capacity=1)
    repos.inscribir(ASISTENTE, evento)
    assert_conflicto(inscribirse(cliente, evento, auth(OTRO_ASISTENTE)), "capacity-full")

    assert cancelar(cliente, evento, auth(ASISTENTE)).status_code == 204

    assert inscribirse(cliente, evento, auth(OTRO_ASISTENTE)).status_code == 201


def test_volver_a_inscribirse_despues_de_cancelar_deja_una_activa_y_una_cancelada(
    cliente, repos, auth
):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento)
    assert cancelar(cliente, evento, auth(ASISTENTE)).status_code == 204

    respuesta = inscribirse(cliente, evento, auth(ASISTENTE))

    assert respuesta.status_code == 201, respuesta.text
    estados = sorted(i.status for i in repos.de(ASISTENTE, evento))
    assert estados == [EstadoInscripcion.ACTIVE, EstadoInscripcion.CANCELLED]


def test_cancelar_sin_inscripcion_activa_responde_404(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento, EstadoInscripcion.CANCELLED)

    respuesta = cancelar(cliente, evento, auth(ASISTENTE))

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "not-found"


def test_cancelar_solo_toca_la_inscripcion_del_usuario_del_token(cliente, repos, auth):
    evento = repos.evento()
    ajena = repos.inscribir(ASISTENTE, evento)

    assert cancelar(cliente, evento, auth(OTRO_ASISTENTE)).status_code == 404

    assert ajena.status == EstadoInscripcion.ACTIVE
    assert ajena.cancelled_at is None


def test_cancelar_con_el_evento_ya_empezado_responde_event_started(cliente, repos, auth):
    evento = repos.evento(empezado=True)
    inscripcion = repos.inscribir(ASISTENTE, evento)

    respuesta = cancelar(cliente, evento, auth(ASISTENTE))

    assert_conflicto(respuesta, "event-started")
    assert inscripcion.status == EstadoInscripcion.ACTIVE
    assert inscripcion.cancelled_at is None


def test_cancelar_en_un_evento_que_no_existe_responde_404(cliente, repos, auth):
    fantasma = repos.evento()
    del repos.eventos.eventos[fantasma.id]

    assert cancelar(cliente, fantasma, auth(ASISTENTE)).status_code == 404


def test_cancelar_sin_token_responde_401(cliente, repos):
    evento = repos.evento()
    inscripcion = repos.inscribir(ASISTENTE, evento)

    assert cancelar(cliente, evento, {}).status_code == 401
    assert inscripcion.status == EstadoInscripcion.ACTIVE


# --- El evento cuenta sus inscritos --------------------------------------------------------


def test_el_detalle_del_evento_cuenta_solo_las_inscripciones_activas(cliente, repos, auth):
    evento = repos.evento(capacity=5)
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento)
    repos.inscribir(ORGANIZADOR, evento, EstadoInscripcion.CANCELLED)
    otro_evento = repos.evento()
    repos.inscribir(ASISTENTE, otro_evento)

    cuerpo = cliente.get(f"/events/{evento.id}").json()

    assert (cuerpo["registered_count"], cuerpo["available_spots"]) == (2, 3)


def test_inscribirse_y_cancelar_se_ven_en_el_detalle_del_evento(cliente, repos, auth):
    evento = repos.evento(capacity=5)

    assert inscribirse(cliente, evento, auth(ASISTENTE)).status_code == 201
    despues_de_inscribirse = cliente.get(f"/events/{evento.id}").json()
    assert cancelar(cliente, evento, auth(ASISTENTE)).status_code == 204
    despues_de_cancelar = cliente.get(f"/events/{evento.id}").json()

    assert despues_de_inscribirse["available_spots"] == 4
    assert despues_de_cancelar["available_spots"] == 5


# --- Reglas del evento que dependen de las inscripciones -----------------------------------


def editar_evento(cliente, evento: Event, cuerpo: dict, headers: dict):
    return cliente.patch(f"/events/{evento.id}", json=cuerpo, headers=headers)


def test_bajar_la_capacidad_por_debajo_de_las_activas_responde_409_y_no_la_cambia(
    cliente, repos, auth
):
    evento = repos.evento(capacity=5)
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento)
    repos.inscribir(ADMIN, evento, EstadoInscripcion.CANCELLED)

    respuesta = editar_evento(cliente, evento, {"capacity": 1}, auth(ORGANIZADOR))

    assert_conflicto(respuesta, "capacity-below-registrations")
    assert "2" in respuesta.json()["detail"]
    assert evento.capacity == 5
    assert repos.eventos.bloqueos == [evento.id]


def test_igualar_la_capacidad_a_las_activas_se_acepta(cliente, repos, auth):
    evento = repos.evento(capacity=5)
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento)
    repos.inscribir(ADMIN, evento, EstadoInscripcion.CANCELLED)

    respuesta = editar_evento(cliente, evento, {"capacity": 2}, auth(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert evento.capacity == 2


def test_despublicar_con_inscripciones_activas_responde_409_has_registrations(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento)

    respuesta = cliente.post(f"/events/{evento.id}/unpublish", headers=auth(ORGANIZADOR))

    assert_conflicto(respuesta, "has-registrations")
    assert evento.status == EstadoEvento.PUBLISHED
    assert repos.eventos.bloqueos == [evento.id]


def test_despublicar_con_solo_inscripciones_canceladas_se_acepta(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento, EstadoInscripcion.CANCELLED)

    respuesta = cliente.post(f"/events/{evento.id}/unpublish", headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert evento.status == EstadoEvento.DRAFT


def test_eliminar_con_inscripciones_activas_responde_409_y_sugiere_cancelar(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento)

    respuesta = cliente.delete(f"/events/{evento.id}", headers=auth(ADMIN))

    assert_conflicto(respuesta, "has-registrations")
    assert respuesta.json()["detail"] == "Cancelá el evento en lugar de eliminarlo"
    assert evento.id in repos.eventos.eventos
    assert repos.eventos.bloqueos == [evento.id]


def test_eliminar_con_solo_inscripciones_canceladas_se_acepta(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento, EstadoInscripcion.CANCELLED)

    respuesta = cliente.delete(f"/events/{evento.id}", headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 204, respuesta.text
    assert evento.id not in repos.eventos.eventos
