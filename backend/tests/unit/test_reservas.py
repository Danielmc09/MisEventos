"""Reservas de sesiones: las reglas de reservar, en su orden, cancelar la propia y la cascada
desde la inscripción al evento."""

from datetime import UTC, datetime, timedelta

import pytest

from app.api.dependencias import (
    repositorio_eventos,
    repositorio_inscripciones,
    repositorio_reservas,
    repositorio_sesiones,
    repositorio_usuarios,
)
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import EstadoInscripcion, Registration
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

ASISTENTE = User(email="asistente@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
OTRO_ASISTENTE = User(email="otro@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
ORGANIZADOR = User(email="orga@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)

# Las 8:00 en Bogotá (13:00 UTC) de dentro de un mes: el evento va de 8:00 a 18:00.
DIA = (datetime.now(UTC) + timedelta(days=30)).replace(hour=13, minute=0, second=0, microsecond=0)


def a_las(hora: int, minutos: int = 0) -> datetime:
    """Una hora de Bogotá del día del evento, en UTC."""
    return DIA + timedelta(hours=hora - 8, minutes=minutos)


class Repos:
    def __init__(self) -> None:
        self.usuarios = RepositorioUsuariosFalso(ASISTENTE, OTRO_ASISTENTE, ORGANIZADOR)
        self.eventos = RepositorioEventosFalso()
        self.sesiones = RepositorioSesionesFalso(self.eventos, RepositorioPonentesFalso())
        self.inscripciones = RepositorioInscripcionesFalso(self.eventos, self.usuarios)
        self.reservas = RepositorioReservasFalso(self.eventos)

    def evento(self, estado: EstadoEvento = EstadoEvento.PUBLISHED, **cambios) -> Event:
        datos = {
            "name": "PyCon Bogotá",
            "start_at": a_las(8),
            "end_at": a_las(18),
            "capacity": 50,
            "status": estado,
            "organizer_id": ORGANIZADOR.id,
        } | cambios
        return self.eventos.crear(Event(**datos))

    def sesion(
        self,
        evento: Event,
        inicio: datetime | None = None,
        fin: datetime | None = None,
        **cambios,
    ) -> Sesion:
        inicio = inicio or a_las(10)
        datos = {
            "title": "Testing en Python",
            "start_at": inicio,
            "end_at": fin or inicio + timedelta(hours=1),
            "event_id": evento.id,
        } | cambios
        sesion = Sesion(**datos)
        self.eventos.sesiones[sesion.id] = sesion
        return sesion

    def inscribir(
        self, usuario: User, evento: Event, estado: EstadoInscripcion = EstadoInscripcion.ACTIVE
    ) -> Registration:
        return self.inscripciones.crear(
            Registration(user_id=usuario.id, event_id=evento.id, status=estado)
        )

    def reservar(
        self, usuario: User, sesion: Sesion, estado: EstadoReserva = EstadoReserva.ACTIVE
    ) -> SessionRegistration:
        return self.reservas.crear(
            SessionRegistration(user_id=usuario.id, session_id=sesion.id, status=estado)
        )

    def de(self, usuario: User, sesion: Sesion) -> list[SessionRegistration]:
        return [
            r
            for r in self.reservas.reservas.values()
            if r.user_id == usuario.id and r.session_id == sesion.id
        ]


@pytest.fixture
def repos(app) -> Repos:
    nuevos = Repos()
    app.dependency_overrides[repositorio_usuarios] = lambda: nuevos.usuarios
    app.dependency_overrides[repositorio_eventos] = lambda: nuevos.eventos
    app.dependency_overrides[repositorio_sesiones] = lambda: nuevos.sesiones
    app.dependency_overrides[repositorio_inscripciones] = lambda: nuevos.inscripciones
    app.dependency_overrides[repositorio_reservas] = lambda: nuevos.reservas
    return nuevos


@pytest.fixture
def auth(settings):
    def de(usuario: User | None) -> dict:
        if usuario is None:
            return {}
        return {"Authorization": f"Bearer {crear_access_token(usuario.id, settings.jwt_secret, 5)}"}

    return de


def reservar(cliente, sesion: Sesion, headers: dict, **kwargs):
    return cliente.post(f"/sessions/{sesion.id}/reservations", headers=headers, **kwargs)


def llena(repos: Repos, sesion: Sesion, lugares: int) -> None:
    """Ocupa `lugares` con reservas de otras personas, inscritas al evento."""
    evento = repos.eventos.eventos[sesion.event_id]
    for _ in range(lugares):
        otro = User(email="x@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
        repos.inscribir(otro, evento)
        repos.reservar(otro, sesion)


def assert_conflicto(respuesta, tipo: str) -> None:
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo["type"] == tipo
    assert cuerpo["title"]
    assert cuerpo.get("detail"), "el 409 explica en el detalle qué pasó"
    assert cuerpo["detail"] != cuerpo["title"]
    assert cuerpo["trace_id"]


# --- Reservar ------------------------------------------------------------------------------


def test_un_inscrito_reserva_una_sesion_con_lugar_y_responde_201(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento, capacity=10)
    repos.inscribir(ASISTENTE, evento)

    respuesta = reservar(cliente, sesion, auth(ASISTENTE))

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "session_id", "status", "created_at"}
    assert cuerpo["session_id"] == str(sesion.id)
    assert cuerpo["status"] == "ACTIVE"
    assert cuerpo["created_at"].endswith("Z")
    [guardada] = repos.de(ASISTENTE, sesion)
    assert str(guardada.id) == cuerpo["id"]
    assert guardada.status == EstadoReserva.ACTIVE


def test_reservar_bloquea_el_evento_la_inscripcion_y_la_sesion_en_ese_orden(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    inscripcion = repos.inscribir(ASISTENTE, evento)

    reservar(cliente, sesion, auth(ASISTENTE))

    assert repos.eventos.bloqueos == [evento.id, inscripcion.id, sesion.id]


def test_sin_inscripcion_y_con_la_sesion_llena_el_error_es_not_registered(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento, capacity=1)
    llena(repos, sesion, 1)

    respuesta = reservar(cliente, sesion, auth(ASISTENTE))

    assert_conflicto(respuesta, "not-registered")
    assert respuesta.json()["title"] == "Inscribite al evento para reservar sesiones"
    assert repos.de(ASISTENTE, sesion) == []


def test_una_inscripcion_cancelada_no_alcanza_para_reservar(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    repos.inscribir(ASISTENTE, evento, EstadoInscripcion.CANCELLED)

    assert_conflicto(reservar(cliente, sesion, auth(ASISTENTE)), "not-registered")


def test_estar_inscrito_a_otro_evento_no_alcanza_para_reservar(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    repos.inscribir(ASISTENTE, repos.evento())

    assert_conflicto(reservar(cliente, sesion, auth(ASISTENTE)), "not-registered")


def test_una_sesion_que_no_existe_responde_404(cliente, repos, auth):
    fantasma = Sesion(
        title="No existe", start_at=a_las(10), end_at=a_las(11), event_id=repos.evento().id
    )

    respuesta = reservar(cliente, fantasma, auth(ASISTENTE))

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "not-found"


def test_una_sesion_de_un_borrador_ajeno_responde_404(cliente, repos, auth):
    borrador = repos.evento(EstadoEvento.DRAFT)
    sesion = repos.sesion(borrador)

    respuesta = reservar(cliente, sesion, auth(ASISTENTE))

    assert respuesta.status_code == 404
    assert repos.eventos.bloqueos == [borrador.id]  # no sigue bloqueando lo que no ve


@pytest.mark.parametrize(
    ("estado", "usuario"),
    [(EstadoEvento.DRAFT, ORGANIZADOR), (EstadoEvento.CANCELLED, ASISTENTE)],
    ids=["borrador-propio", "cancelado"],
)
def test_un_evento_no_publicado_responde_event_not_open_aunque_este_inscrito(
    cliente, repos, auth, estado, usuario
):
    evento = repos.evento(estado)
    sesion = repos.sesion(evento)
    repos.inscribir(usuario, evento)

    respuesta = reservar(cliente, sesion, auth(usuario))

    assert_conflicto(respuesta, "event-not-open")
    assert repos.de(usuario, sesion) == []


def test_una_sesion_que_ya_empezo_responde_session_started_aunque_no_este_inscrito(
    cliente, repos, auth
):
    ahora = datetime.now(UTC)
    evento = repos.evento(start_at=ahora - timedelta(hours=2), end_at=ahora + timedelta(hours=6))
    sesion = repos.sesion(evento, ahora - timedelta(minutes=5), ahora + timedelta(hours=1))

    assert_conflicto(reservar(cliente, sesion, auth(ASISTENTE)), "session-started")


def test_reservar_dos_veces_responde_already_reserved_aunque_este_llena(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento, capacity=1)
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, sesion)

    respuesta = reservar(cliente, sesion, auth(ASISTENTE))

    assert_conflicto(respuesta, "already-reserved")
    assert len(repos.de(ASISTENTE, sesion)) == 1


def test_una_sesion_llena_responde_session_full_con_la_capacidad_en_el_detalle(
    cliente, repos, auth
):
    evento = repos.evento()
    sesion = repos.sesion(evento, capacity=3)
    llena(repos, sesion, 3)
    repos.inscribir(ASISTENTE, evento)

    respuesta = reservar(cliente, sesion, auth(ASISTENTE))

    assert_conflicto(respuesta, "session-full")
    assert "3" in respuesta.json()["detail"]
    assert repos.de(ASISTENTE, sesion) == []


def test_una_sesion_sin_capacidad_propia_se_llena_con_la_del_evento(cliente, repos, auth):
    # El doble no controla el cupo del evento: deja inscribir de más para llegar a la regla.
    evento = repos.evento(capacity=2)
    sesion = repos.sesion(evento, capacity=None)
    llena(repos, sesion, 2)
    repos.inscribir(ASISTENTE, evento)

    respuesta = reservar(cliente, sesion, auth(ASISTENTE))

    assert_conflicto(respuesta, "session-full")
    assert "2" in respuesta.json()["detail"]


def test_una_sesion_sin_capacidad_propia_con_lugar_en_el_evento_se_reserva(cliente, repos, auth):
    evento = repos.evento(capacity=2)
    sesion = repos.sesion(evento, capacity=None)
    llena(repos, sesion, 1)
    repos.inscribir(ASISTENTE, evento)

    assert reservar(cliente, sesion, auth(ASISTENTE)).status_code == 201


def test_las_reservas_canceladas_no_ocupan_lugar(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento, capacity=1)
    repos.inscribir(OTRO_ASISTENTE, evento)
    repos.reservar(OTRO_ASISTENTE, sesion, EstadoReserva.CANCELLED)
    repos.inscribir(ASISTENTE, evento)

    assert reservar(cliente, sesion, auth(ASISTENTE)).status_code == 201


def test_el_ultimo_lugar_entra(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento, capacity=2)
    llena(repos, sesion, 1)
    repos.inscribir(ASISTENTE, evento)

    assert reservar(cliente, sesion, auth(ASISTENTE)).status_code == 201


# --- Cruces dentro del evento -----------------------------------------------------------------


def test_una_sesion_que_se_cruza_con_otra_reserva_del_evento_responde_session_conflict(
    cliente, repos, auth
):
    evento = repos.evento()
    reservada = repos.sesion(evento, a_las(10), a_las(11), title="Testing en Python", room="C")
    paralela = repos.sesion(evento, a_las(10, 30), a_las(11, 30), title="Django", room="B")
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, reservada)

    respuesta = reservar(cliente, paralela, auth(ASISTENTE))

    assert_conflicto(respuesta, "session-conflict")
    assert respuesta.json()["conflicts"] == [
        {
            "session_id": str(reservada.id),
            "title": "Testing en Python",
            "start_at": reservada.start_at.isoformat().replace("+00:00", "Z"),
            "end_at": reservada.end_at.isoformat().replace("+00:00", "Z"),
            "room": "C",
        }
    ]
    assert "Testing en Python" in respuesta.json()["detail"]
    assert repos.de(ASISTENTE, paralela) == []


def test_session_conflict_trae_todas_las_que_chocan_por_hora_y_la_sala_vacia_como_null(
    cliente, repos, auth
):
    evento = repos.evento()
    segunda = repos.sesion(evento, a_las(11), a_las(12), title="Segunda")
    primera = repos.sesion(evento, a_las(10), a_las(11), title="Primera", room="A")
    larga = repos.sesion(evento, a_las(10), a_las(12), title="Larga")
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, segunda)
    repos.reservar(ASISTENTE, primera)

    respuesta = reservar(cliente, larga, auth(ASISTENTE))

    assert_conflicto(respuesta, "session-conflict")
    conflictos = respuesta.json()["conflicts"]
    assert [c["title"] for c in conflictos] == ["Primera", "Segunda"]
    assert conflictos[1]["room"] is None


def test_sesiones_que_se_tocan_no_se_cruzan(cliente, repos, auth):
    evento = repos.evento()
    antes = repos.sesion(evento, a_las(9), a_las(10))
    despues = repos.sesion(evento, a_las(10), a_las(11))
    repos.inscribir(ASISTENTE, evento)

    assert reservar(cliente, antes, auth(ASISTENTE)).status_code == 201
    assert reservar(cliente, despues, auth(ASISTENTE)).status_code == 201


def test_una_sesion_que_se_cruza_con_una_reserva_de_otro_evento_se_reserva(cliente, repos, auth):
    evento = repos.evento()
    otro = repos.evento(name="Python Day")
    de_otro = repos.sesion(otro, a_las(10), a_las(11))
    sesion = repos.sesion(evento, a_las(10), a_las(11))
    repos.inscribir(ASISTENTE, otro)
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, de_otro)

    assert reservar(cliente, sesion, auth(ASISTENTE)).status_code == 201


def test_una_reserva_cancelada_no_choca(cliente, repos, auth):
    evento = repos.evento()
    cancelada = repos.sesion(evento, a_las(10), a_las(11))
    sesion = repos.sesion(evento, a_las(10), a_las(11))
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, cancelada, EstadoReserva.CANCELLED)

    assert reservar(cliente, sesion, auth(ASISTENTE)).status_code == 201


def test_la_reserva_de_otra_persona_no_choca(cliente, repos, auth):
    evento = repos.evento()
    ajena = repos.sesion(evento, a_las(10), a_las(11))
    sesion = repos.sesion(evento, a_las(10), a_las(11))
    repos.inscribir(OTRO_ASISTENTE, evento)
    repos.reservar(OTRO_ASISTENTE, ajena)
    repos.inscribir(ASISTENTE, evento)

    assert reservar(cliente, sesion, auth(ASISTENTE)).status_code == 201


def test_una_sesion_llena_que_ademas_se_cruza_responde_session_full(cliente, repos, auth):
    evento = repos.evento()
    reservada = repos.sesion(evento, a_las(10), a_las(11))
    llena_y_paralela = repos.sesion(evento, a_las(10), a_las(11), capacity=1)
    llena(repos, llena_y_paralela, 1)
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, reservada)

    assert_conflicto(reservar(cliente, llena_y_paralela, auth(ASISTENTE)), "session-full")


# --- El cuerpo y la autenticación -----------------------------------------------------------


def test_reservar_no_acepta_confirm_overlap_ni_ningun_otro_campo(cliente, repos, auth):
    evento = repos.evento()
    reservada = repos.sesion(evento, a_las(10), a_las(11))
    paralela = repos.sesion(evento, a_las(10), a_las(11))
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, reservada)

    respuesta = reservar(cliente, paralela, auth(ASISTENTE), json={"confirm_overlap": True})

    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["errors"][0]["field"] == "confirm_overlap"
    assert repos.de(ASISTENTE, paralela) == []


def test_un_cuerpo_vacio_se_acepta(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    repos.inscribir(ASISTENTE, evento)

    assert reservar(cliente, sesion, auth(ASISTENTE), json={}).status_code == 201


def test_reservar_sin_token_responde_401(cliente, repos):
    evento = repos.evento()
    sesion = repos.sesion(evento)

    assert reservar(cliente, sesion, {}).status_code == 401
    assert repos.reservas.reservas == {}
