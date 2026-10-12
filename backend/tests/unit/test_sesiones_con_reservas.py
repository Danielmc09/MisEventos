"""Una sesión con reservas activas: no cambia de horario, no se elimina y su capacidad no baja de
lo reservado; el título sí se edita. El evento tampoco baja su capacidad por debajo de las reservas
de una sesión que usa la del evento. Las reservas canceladas no cuentan para nada de esto."""

from datetime import UTC, datetime, timedelta

import pytest

from app.api.dependencias import (
    repositorio_eventos,
    repositorio_inscripciones,
    repositorio_ponentes,
    repositorio_reservas,
    repositorio_sesiones,
    repositorio_usuarios,
)
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import Registration
from app.models.reserva import EstadoReserva, SessionRegistration
from app.models.sesion import Session as Sesion
from app.models.usuario import User
from tests.unit.dobles import (
    RepositorioEventosFalso,
    RepositorioInscripcionesFalso,
    RepositorioPonentesFalso,
    RepositorioReservasFalso,
    RepositorioSesionesFalso,
    RepositorioUsuariosFalso,
)

ORGANIZADOR = User(email="orga@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)

# Las 8:00 en Bogotá (13:00 UTC) de dentro de un mes: el evento va de 8:00 a 18:00.
DIA = (datetime.now(UTC) + timedelta(days=30)).replace(hour=13, minute=0, second=0, microsecond=0)


def a_las(hora: int, minutos: int = 0) -> datetime:
    """Una hora de Bogotá del día del evento, en UTC."""
    return DIA + timedelta(hours=hora - 8, minutes=minutos)


class Repos:
    def __init__(self) -> None:
        self.usuarios = RepositorioUsuariosFalso(ORGANIZADOR)
        self.eventos = RepositorioEventosFalso()
        self.ponentes = RepositorioPonentesFalso()
        self.sesiones = RepositorioSesionesFalso(self.eventos, self.ponentes)
        self.ponentes.bloqueos = self.eventos.bloqueos
        self.inscripciones = RepositorioInscripcionesFalso(self.eventos, self.usuarios)
        self.reservas = RepositorioReservasFalso(self.eventos)

    def evento(self, **cambios) -> Event:
        datos = {
            "name": "PyCon Bogotá",
            "start_at": a_las(8),
            "end_at": a_las(18),
            "capacity": 50,
            "status": EstadoEvento.PUBLISHED,
            "organizer_id": ORGANIZADOR.id,
        } | cambios
        return self.eventos.crear(Event(**datos))

    def sesion(self, evento: Event, **cambios) -> Sesion:
        datos = {
            "title": "Testing en Python",
            "start_at": a_las(10),
            "end_at": a_las(11),
            "event_id": evento.id,
        } | cambios
        return self.sesiones.crear(Sesion(**datos), [])

    def reservas_en(
        self, sesion: Sesion, cuantas: int, estado: EstadoReserva = EstadoReserva.ACTIVE
    ) -> None:
        """`cuantas` personas inscritas al evento, cada una con una reserva en la sesión."""
        for _ in range(cuantas):
            asistente = User(email="x@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
            self.inscripciones.crear(Registration(user_id=asistente.id, event_id=sesion.event_id))
            self.reservas.crear(
                SessionRegistration(user_id=asistente.id, session_id=sesion.id, status=estado)
            )


@pytest.fixture
def repos(app) -> Repos:
    nuevos = Repos()
    app.dependency_overrides[repositorio_usuarios] = lambda: nuevos.usuarios
    app.dependency_overrides[repositorio_eventos] = lambda: nuevos.eventos
    app.dependency_overrides[repositorio_ponentes] = lambda: nuevos.ponentes
    app.dependency_overrides[repositorio_sesiones] = lambda: nuevos.sesiones
    app.dependency_overrides[repositorio_inscripciones] = lambda: nuevos.inscripciones
    app.dependency_overrides[repositorio_reservas] = lambda: nuevos.reservas
    return nuevos


@pytest.fixture
def orga(settings) -> dict:
    return {"Authorization": f"Bearer {crear_access_token(ORGANIZADOR.id, settings.jwt_secret, 5)}"}


def editar_sesion(cliente, sesion: Sesion, datos: dict, headers: dict):
    return cliente.patch(f"/sessions/{sesion.id}", json=datos, headers=headers)


def editar_evento(cliente, evento: Event, datos: dict, headers: dict):
    return cliente.patch(f"/events/{evento.id}", json=datos, headers=headers)


def assert_conflicto(respuesta, tipo: str) -> None:
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo["type"] == tipo
    assert cuerpo["title"]
    assert cuerpo.get("detail"), "el 409 explica en el detalle qué pasó"
    assert cuerpo["trace_id"]


# --- El horario ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cambio",
    [
        {"start_at": a_las(9, 30).isoformat()},
        {"end_at": a_las(11, 30).isoformat()},
        {"start_at": a_las(12).isoformat(), "end_at": a_las(13).isoformat()},
    ],
    ids=["inicio", "fin", "los-dos"],
)
def test_con_reservas_activas_no_se_cambia_el_horario(cliente, repos, orga, cambio):
    sesion = repos.sesion(repos.evento())
    repos.reservas_en(sesion, 1)

    respuesta = editar_sesion(cliente, sesion, cambio, orga)

    assert_conflicto(respuesta, "session-has-reservations")
    assert (sesion.start_at, sesion.end_at) == (a_las(10), a_las(11))


def test_mandar_el_mismo_horario_no_es_cambiarlo(cliente, repos, orga):
    sesion = repos.sesion(repos.evento())
    repos.reservas_en(sesion, 1)
    mismo = {"start_at": a_las(10).isoformat(), "end_at": a_las(11).isoformat(), "title": "Otro"}

    respuesta = editar_sesion(cliente, sesion, mismo, orga)

    assert respuesta.status_code == 200, respuesta.text
    assert sesion.title == "Otro"


def test_con_reservas_activas_el_titulo_si_se_cambia(cliente, repos, orga):
    sesion = repos.sesion(repos.evento())
    repos.reservas_en(sesion, 3)

    respuesta = editar_sesion(cliente, sesion, {"title": "Pytest avanzado"}, orga)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["title"] == "Pytest avanzado"


def test_con_reservas_solo_canceladas_el_horario_se_cambia(cliente, repos, orga):
    sesion = repos.sesion(repos.evento())
    repos.reservas_en(sesion, 2, EstadoReserva.CANCELLED)

    respuesta = editar_sesion(cliente, sesion, {"start_at": a_las(9, 30).isoformat()}, orga)

    assert respuesta.status_code == 200, respuesta.text
    assert sesion.start_at == a_las(9, 30)


# --- Eliminar ------------------------------------------------------------------------------


def test_con_reservas_activas_no_se_elimina(cliente, repos, orga):
    sesion = repos.sesion(repos.evento())
    repos.reservas_en(sesion, 1)

    respuesta = cliente.delete(f"/sessions/{sesion.id}", headers=orga)

    assert_conflicto(respuesta, "session-has-reservations")
    assert sesion.id in repos.eventos.sesiones


def test_con_reservas_solo_canceladas_se_elimina(cliente, repos, orga):
    sesion = repos.sesion(repos.evento())
    repos.reservas_en(sesion, 2, EstadoReserva.CANCELLED)

    respuesta = cliente.delete(f"/sessions/{sesion.id}", headers=orga)

    assert respuesta.status_code == 204, respuesta.text
    assert sesion.id not in repos.eventos.sesiones


# --- La capacidad de la sesión -------------------------------------------------------------


def test_la_capacidad_de_la_sesion_no_baja_de_sus_reservas_activas(cliente, repos, orga):
    sesion = repos.sesion(repos.evento(), capacity=10)
    repos.reservas_en(sesion, 5)

    respuesta = editar_sesion(cliente, sesion, {"capacity": 4}, orga)

    assert_conflicto(respuesta, "capacity-below-reservations")
    assert "5" in respuesta.json()["detail"]
    assert sesion.capacity == 10


def test_la_capacidad_de_la_sesion_puede_quedar_igual_a_sus_reservas(cliente, repos, orga):
    sesion = repos.sesion(repos.evento(), capacity=10)
    repos.reservas_en(sesion, 5)

    respuesta = editar_sesion(cliente, sesion, {"capacity": 5}, orga)

    assert respuesta.status_code == 200, respuesta.text
    assert sesion.capacity == 5


def test_las_reservas_canceladas_no_frenan_bajar_la_capacidad_de_la_sesion(cliente, repos, orga):
    sesion = repos.sesion(repos.evento(), capacity=10)
    repos.reservas_en(sesion, 2)
    repos.reservas_en(sesion, 6, EstadoReserva.CANCELLED)

    respuesta = editar_sesion(cliente, sesion, {"capacity": 2}, orga)

    assert respuesta.status_code == 200, respuesta.text
    assert sesion.capacity == 2


def test_sacarle_la_capacidad_propia_usa_la_del_evento(cliente, repos, orga):
    sesion = repos.sesion(repos.evento(capacity=50), capacity=10)
    repos.reservas_en(sesion, 10)

    respuesta = editar_sesion(cliente, sesion, {"capacity": None}, orga)

    assert respuesta.status_code == 200, respuesta.text
    assert sesion.capacity is None


# --- La capacidad del evento ---------------------------------------------------------------


def test_la_capacidad_del_evento_no_baja_de_las_reservas_de_una_sesion_sin_capacidad_propia(
    cliente, repos, orga
):
    evento = repos.evento(capacity=50)
    repos.reservas_en(repos.sesion(evento), 3)
    repos.reservas_en(repos.sesion(evento, start_at=a_las(12), end_at=a_las(13)), 5)

    respuesta = editar_evento(cliente, evento, {"capacity": 4}, orga)

    assert_conflicto(respuesta, "capacity-below-reservations")
    assert "5" in respuesta.json()["detail"]
    assert evento.capacity == 50


def test_la_capacidad_del_evento_puede_quedar_igual_a_las_reservas_de_una_sesion(
    cliente, repos, orga
):
    evento = repos.evento(capacity=50)
    repos.reservas_en(repos.sesion(evento), 5)

    respuesta = editar_evento(cliente, evento, {"capacity": 5}, orga)

    assert respuesta.status_code == 200, respuesta.text
    assert evento.capacity == 5


def test_las_reservas_canceladas_no_frenan_bajar_la_capacidad_del_evento(cliente, repos, orga):
    evento = repos.evento(capacity=50)
    sesion = repos.sesion(evento)
    repos.reservas_en(sesion, 2)
    # Las de quien canceló: sin inscripción activa, así tampoco cuentan como inscritos.
    for reserva in [
        SessionRegistration(user_id=User().id, session_id=sesion.id, status=EstadoReserva.CANCELLED)
        for _ in range(6)
    ]:
        repos.reservas.crear(reserva)

    respuesta = editar_evento(cliente, evento, {"capacity": 2}, orga)

    assert respuesta.status_code == 200, respuesta.text
    assert evento.capacity == 2


def test_por_debajo_de_reservas_y_de_inscritos_el_error_es_el_de_las_reservas(cliente, repos, orga):
    # Toda reserva activa cuelga de una inscripción activa: quedar por debajo de las reservas
    # de una sesión es también quedar por debajo de los inscritos. Las reservas van primero o
    # su error no saldría nunca.
    evento = repos.evento(capacity=50)
    repos.reservas_en(repos.sesion(evento), 5)

    respuesta = editar_evento(cliente, evento, {"capacity": 4}, orga)

    assert_conflicto(respuesta, "capacity-below-reservations")


# --- Orden de los bloqueos: evento → sesión, y recién ahí se cuenta ------------------------


def test_cambiar_el_horario_cuenta_las_reservas_con_el_evento_y_la_sesion_bloqueados(
    cliente, repos, orga
):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    repos.reservas_en(sesion, 1)

    editar_sesion(cliente, sesion, {"start_at": a_las(9, 30).isoformat()}, orga)

    assert repos.reservas.bloqueos_al_contar == [[evento.id, sesion.id]]


def test_bajar_la_capacidad_de_la_sesion_cuenta_con_el_evento_y_la_sesion_bloqueados(
    cliente, repos, orga
):
    evento = repos.evento()
    sesion = repos.sesion(evento, capacity=10)
    repos.reservas_en(sesion, 1)

    editar_sesion(cliente, sesion, {"capacity": 5}, orga)

    assert repos.reservas.bloqueos_al_contar == [[evento.id, sesion.id]]


def test_eliminar_cuenta_las_reservas_con_el_evento_y_la_sesion_bloqueados(cliente, repos, orga):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    repos.reservas_en(sesion, 1)

    cliente.delete(f"/sessions/{sesion.id}", headers=orga)

    assert repos.reservas.bloqueos_al_contar == [[evento.id, sesion.id]]


def test_cambiar_solo_el_titulo_no_cuenta_reservas(cliente, repos, orga):
    sesion = repos.sesion(repos.evento())

    editar_sesion(cliente, sesion, {"title": "Pytest avanzado"}, orga)

    assert repos.reservas.bloqueos_al_contar == []


def test_bajar_la_capacidad_del_evento_cuenta_las_reservas_con_el_evento_bloqueado(
    cliente, repos, orga
):
    evento = repos.evento(capacity=50)
    repos.reservas_en(repos.sesion(evento), 1)

    editar_evento(cliente, evento, {"capacity": 40}, orga)

    assert repos.eventos.bloqueos_al_contar_reservas == [[evento.id]]
