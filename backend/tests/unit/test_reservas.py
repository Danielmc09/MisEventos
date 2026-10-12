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
        return self.sesiones.crear(Sesion(**datos), [])

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


@pytest.mark.parametrize(
    ("capacidad", "personas"), [(1, "1 persona"), (2, "2 personas")], ids=["una", "dos"]
)
def test_el_detalle_de_una_sesion_llena_habla_en_singular_con_una_persona(
    cliente, repos, auth, capacidad, personas
):
    evento = repos.evento()
    sesion = repos.sesion(evento, capacity=capacidad)
    llena(repos, sesion, capacidad)
    repos.inscribir(ASISTENTE, evento)

    respuesta = reservar(cliente, sesion, auth(ASISTENTE))

    assert respuesta.json()["detail"] == f"La sesión alcanzó su capacidad de {personas}."


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


# --- Cancelar la reserva ----------------------------------------------------------------------


def cancelar(cliente, sesion: Sesion, headers: dict):
    return cliente.delete(f"/sessions/{sesion.id}/reservations/me", headers=headers)


def test_cancelar_la_propia_responde_204_y_la_deja_cancelada_con_fecha(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    inscripcion = repos.inscribir(ASISTENTE, evento)
    reserva = repos.reservar(ASISTENTE, sesion)
    antes = datetime.now(UTC)

    respuesta = cancelar(cliente, sesion, auth(ASISTENTE))

    assert respuesta.status_code == 204, respuesta.text
    assert respuesta.content == b""
    assert reserva.status == EstadoReserva.CANCELLED
    assert reserva.cancelled_at is not None
    assert reserva.cancelled_at >= antes
    assert repos.eventos.bloqueos == [evento.id, inscripcion.id, sesion.id]


def test_cancelar_libera_el_lugar_y_se_puede_volver_a_reservar(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento, capacity=1)
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento)
    assert reservar(cliente, sesion, auth(ASISTENTE)).status_code == 201
    assert_conflicto(reservar(cliente, sesion, auth(OTRO_ASISTENTE)), "session-full")

    assert cancelar(cliente, sesion, auth(ASISTENTE)).status_code == 204

    assert reservar(cliente, sesion, auth(OTRO_ASISTENTE)).status_code == 201
    assert cancelar(cliente, sesion, auth(OTRO_ASISTENTE)).status_code == 204
    assert reservar(cliente, sesion, auth(ASISTENTE)).status_code == 201
    estados = sorted(r.status for r in repos.de(ASISTENTE, sesion))
    assert estados == [EstadoReserva.ACTIVE, EstadoReserva.CANCELLED]


def test_cancelar_sin_reserva_activa_responde_404(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, sesion, EstadoReserva.CANCELLED)

    respuesta = cancelar(cliente, sesion, auth(ASISTENTE))

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "not-found"


def test_cancelar_solo_toca_la_reserva_del_usuario_del_token(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    repos.inscribir(ASISTENTE, evento)
    ajena = repos.reservar(ASISTENTE, sesion)
    repos.inscribir(OTRO_ASISTENTE, evento)

    assert cancelar(cliente, sesion, auth(OTRO_ASISTENTE)).status_code == 404

    assert ajena.status == EstadoReserva.ACTIVE
    assert ajena.cancelled_at is None


def empezada(repos: Repos) -> tuple[Event, Sesion]:
    ahora = datetime.now(UTC)
    evento = repos.evento(start_at=ahora - timedelta(hours=2), end_at=ahora + timedelta(hours=6))
    return evento, repos.sesion(evento, ahora - timedelta(minutes=5), ahora + timedelta(hours=1))


def test_cancelar_con_la_sesion_empezada_responde_session_started(cliente, repos, auth):
    evento, sesion = empezada(repos)
    repos.inscribir(ASISTENTE, evento)
    reserva = repos.reservar(ASISTENTE, sesion)

    respuesta = cancelar(cliente, sesion, auth(ASISTENTE))

    assert_conflicto(respuesta, "session-started")
    assert reserva.status == EstadoReserva.ACTIVE
    assert reserva.cancelled_at is None


def test_cancelar_sin_reserva_con_la_sesion_empezada_responde_404(cliente, repos, auth):
    evento, sesion = empezada(repos)
    repos.inscribir(ASISTENTE, evento)

    assert cancelar(cliente, sesion, auth(ASISTENTE)).status_code == 404


def test_cancelar_en_una_sesion_que_no_existe_responde_404(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, sesion)
    del repos.eventos.sesiones[sesion.id]

    assert cancelar(cliente, sesion, auth(ASISTENTE)).status_code == 404


def test_cancelar_sin_token_responde_401(cliente, repos):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    repos.inscribir(ASISTENTE, evento)
    reserva = repos.reservar(ASISTENTE, sesion)

    assert cancelar(cliente, sesion, {}).status_code == 401
    assert reserva.status == EstadoReserva.ACTIVE


# --- Cascada desde la inscripción al evento ---------------------------------------------------


def cancelar_inscripcion(cliente, evento: Event, headers: dict):
    return cliente.delete(f"/events/{evento.id}/registrations/me", headers=headers)


def test_cancelar_la_inscripcion_cancela_las_reservas_del_usuario_en_ese_evento(
    cliente, repos, auth
):
    evento = repos.evento()
    manana = repos.sesion(evento, a_las(10), a_las(11))
    tarde = repos.sesion(evento, a_las(15), a_las(16))
    repos.inscribir(ASISTENTE, evento)
    propias = [repos.reservar(ASISTENTE, manana), repos.reservar(ASISTENTE, tarde)]
    antes = datetime.now(UTC)

    assert cancelar_inscripcion(cliente, evento, auth(ASISTENTE)).status_code == 204

    assert [r.status for r in propias] == [EstadoReserva.CANCELLED] * 2
    assert all(r.cancelled_at is not None and r.cancelled_at >= antes for r in propias)


def test_la_cascada_no_toca_otros_eventos_ni_otras_personas(cliente, repos, auth):
    evento = repos.evento()
    otro = repos.evento(name="Python Day")
    sesion = repos.sesion(evento)
    de_otro = repos.sesion(otro)
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(ASISTENTE, otro)
    repos.inscribir(OTRO_ASISTENTE, evento)
    propia_de_otro_evento = repos.reservar(ASISTENTE, de_otro)
    ajena = repos.reservar(OTRO_ASISTENTE, sesion)
    repos.reservar(ASISTENTE, sesion)

    assert cancelar_inscripcion(cliente, evento, auth(ASISTENTE)).status_code == 204

    assert propia_de_otro_evento.status == EstadoReserva.ACTIVE
    assert ajena.status == EstadoReserva.ACTIVE
    assert repos.reservas.activas_en(sesion.id) == 1


def test_cancelar_la_inscripcion_bloquea_el_evento_y_despues_la_inscripcion(cliente, repos, auth):
    evento = repos.evento()
    inscripcion = repos.inscribir(ASISTENTE, evento)

    assert cancelar_inscripcion(cliente, evento, auth(ASISTENTE)).status_code == 204

    assert repos.eventos.bloqueos == [evento.id, inscripcion.id]


def test_sin_cancelar_la_inscripcion_las_reservas_quedan_activas(cliente, repos, auth):
    ahora = datetime.now(UTC)
    evento = repos.evento(start_at=ahora - timedelta(hours=1), end_at=ahora + timedelta(hours=6))
    sesion = repos.sesion(evento, ahora + timedelta(hours=1), ahora + timedelta(hours=2))
    repos.inscribir(ASISTENTE, evento)
    reserva = repos.reservar(ASISTENTE, sesion)

    assert_conflicto(cancelar_inscripcion(cliente, evento, auth(ASISTENTE)), "event-started")

    assert reserva.status == EstadoReserva.ACTIVE


# --- Consultas: el listado de sesiones, mis inscripciones y las estadísticas ------------------


def iso(fecha: datetime) -> str:
    return fecha.isoformat().replace("+00:00", "Z")


def listado(cliente, evento: Event, headers: dict) -> dict[str, dict]:
    """Las sesiones del evento, por título."""
    respuesta = cliente.get(f"/events/{evento.id}/sessions", headers=headers)
    assert respuesta.status_code == 200, respuesta.text
    return {s["title"]: s for s in respuesta.json()}


def cupo(sesion: dict) -> tuple:
    return (sesion.get("reserved_count"), sesion.get("available_spots"), sesion.get("is_reserved"))


def test_cada_sesion_del_listado_trae_sus_reservas_sus_lugares_y_si_la_reserve(
    cliente, repos, auth
):
    evento = repos.evento(capacity=50)
    propia = repos.sesion(evento, a_las(9), title="Propia", capacity=10)
    sin_capacidad = repos.sesion(evento, a_las(11), title="Sin capacidad propia")
    vacia = repos.sesion(evento, a_las(14), title="Vacía", capacity=5)
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, propia)
    llena(repos, propia, 2)
    llena(repos, sin_capacidad, 3)
    repos.reservar(ASISTENTE, vacia, EstadoReserva.CANCELLED)

    sesiones = listado(cliente, evento, auth(ASISTENTE))

    assert {titulo: cupo(s) for titulo, s in sesiones.items()} == {
        "Propia": (3, 7, True),
        "Sin capacidad propia": (3, 47, False),
        "Vacía": (0, 5, False),
    }


def test_para_un_anonimo_ninguna_sesion_esta_reservada(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento, capacity=10)
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, sesion)

    [anonima] = listado(cliente, evento, {}).values()
    [del_asistente] = listado(cliente, evento, auth(ASISTENTE)).values()

    assert cupo(anonima) == (1, 9, False)
    assert cupo(del_asistente) == (1, 9, True)
    assert repos.reservas.consultas_de_ocupacion[0]["id_usuario"] is None


def test_el_listado_pide_la_ocupacion_de_todas_las_sesiones_en_una_sola_llamada(
    cliente, repos, auth
):
    evento = repos.evento()
    sesiones = [repos.sesion(evento, a_las(9 + n), title=f"Sesión {n}") for n in range(4)]

    listado(cliente, evento, auth(ASISTENTE))

    assert repos.reservas.consultas_de_ocupacion == [
        {"ids_sesion": [s.id for s in sesiones], "id_usuario": ASISTENTE.id}
    ]


def reservada(sesion: Sesion) -> dict:
    return {
        "id": str(sesion.id),
        "title": sesion.title,
        "start_at": iso(sesion.start_at),
        "end_at": iso(sesion.end_at),
        "room": sesion.room,
    }


def test_cada_inscripcion_trae_sus_sesiones_reservadas_por_hora_de_inicio(cliente, repos, auth):
    evento = repos.evento()
    otro = repos.evento(name="Python Day")
    sin_reservas = repos.evento(name="Sin reservas")
    tarde = repos.sesion(evento, a_las(15), title="Tarde", room="Sala A")
    manana = repos.sesion(evento, a_las(9), title="Mañana")
    cancelada = repos.sesion(evento, a_las(11), title="Cancelada")
    de_otra_persona = repos.sesion(evento, a_las(13), title="De otra persona")
    del_otro_evento = repos.sesion(otro, a_las(10), title="Del otro evento")
    for propio in (evento, otro, sin_reservas):
        repos.inscribir(ASISTENTE, propio)
    repos.inscribir(OTRO_ASISTENTE, evento)
    repos.reservar(ASISTENTE, tarde)
    repos.reservar(ASISTENTE, manana)
    repos.reservar(ASISTENTE, cancelada, EstadoReserva.CANCELLED)
    repos.reservar(OTRO_ASISTENTE, de_otra_persona)
    repos.reservar(ASISTENTE, del_otro_evento)

    respuesta = cliente.get("/me/registrations", headers=auth(ASISTENTE))

    assert respuesta.status_code == 200, respuesta.text
    por_evento = {i["event_id"]: i.get("reserved_sessions") for i in respuesta.json()["items"]}
    assert por_evento == {
        str(evento.id): [reservada(manana), reservada(tarde)],
        str(otro.id): [reservada(del_otro_evento)],
        str(sin_reservas.id): [],
    }


def test_mis_inscripciones_pide_las_reservas_de_toda_la_pagina_en_una_sola_llamada(
    cliente, repos, auth
):
    eventos = [repos.evento(name=f"Evento {n}") for n in range(3)]
    for evento in eventos:
        repos.inscribir(ASISTENTE, evento)

    respuesta = cliente.get("/me/registrations", headers=auth(ASISTENTE))

    assert respuesta.status_code == 200, respuesta.text
    assert len(repos.reservas.consultas_de_reservadas) == 1
    [consulta] = repos.reservas.consultas_de_reservadas
    assert consulta["id_usuario"] == ASISTENTE.id
    assert sorted(consulta["ids_evento"]) == sorted(e.id for e in eventos)


def test_una_inscripcion_cancelada_no_muestra_las_reservas_de_la_inscripcion_nueva(
    cliente, repos, auth
):
    evento = repos.evento()
    sesion = repos.sesion(evento)
    vieja = repos.inscribir(ASISTENTE, evento, EstadoInscripcion.CANCELLED)
    nueva = repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, sesion)

    canceladas = cliente.get(
        "/me/registrations", params={"status": "CANCELLED"}, headers=auth(ASISTENTE)
    )
    activas = cliente.get("/me/registrations", headers=auth(ASISTENTE))

    assert canceladas.status_code == activas.status_code == 200
    assert [(i["id"], i.get("reserved_sessions")) for i in canceladas.json()["items"]] == [
        (str(vieja.id), [])
    ]
    assert [(i["id"], i.get("reserved_sessions")) for i in activas.json()["items"]] == [
        (str(nueva.id), [reservada(sesion)])
    ]


def test_las_estadisticas_traen_la_ocupacion_de_cada_sesion_por_hora_de_inicio(
    cliente, repos, auth
):
    evento = repos.evento(capacity=8)
    tarde = repos.sesion(evento, a_las(15), title="Tarde", capacity=3)
    manana = repos.sesion(evento, a_las(9), title="Mañana")  # sin capacidad propia
    vacia = repos.sesion(evento, a_las(12), title="Vacía", capacity=4)
    llena(repos, tarde, 1)
    llena(repos, manana, 1)
    repos.inscribir(ASISTENTE, evento)
    repos.reservar(ASISTENTE, tarde, EstadoReserva.CANCELLED)

    respuesta = cliente.get(f"/events/{evento.id}/stats", headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json().get("sessions") == [
        {
            "id": str(manana.id),
            "title": "Mañana",
            "reserved": 1,
            "capacity": 8,
            "occupancy_pct": 12.5,
        },
        {"id": str(vacia.id), "title": "Vacía", "reserved": 0, "capacity": 4, "occupancy_pct": 0.0},
        {
            "id": str(tarde.id),
            "title": "Tarde",
            "reserved": 1,
            "capacity": 3,
            "occupancy_pct": 33.3,
        },
    ]


def test_las_estadisticas_de_un_evento_sin_sesiones_traen_la_lista_vacia(cliente, repos, auth):
    evento = repos.evento()

    respuesta = cliente.get(f"/events/{evento.id}/stats", headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json().get("sessions") == []


def _componente(esquema: dict, ref: str) -> dict:
    return esquema["components"]["schemas"][ref.rsplit("/", 1)[-1]]


def _respuesta_200(esquema: dict, ruta: str) -> dict:
    return esquema["paths"][ruta]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]


def _tipos(componente: dict) -> dict[str, object]:
    """Cada propiedad con su tipo, o los tipos de su anyOf si admite null."""

    def tipo(propiedad: dict) -> object:
        if "anyOf" in propiedad:
            return sorted(p.get("type", "?") for p in propiedad["anyOf"])
        return propiedad.get("type")

    return {nombre: tipo(p) for nombre, p in componente["properties"].items()}


def test_el_openapi_tipa_los_campos_nuevos_de_las_tres_consultas(cliente):
    esquema = cliente.get("/openapi.json").json()

    sesion = _componente(
        esquema, _respuesta_200(esquema, "/events/{id_evento}/sessions")["items"]["$ref"]
    )
    tipos = _tipos(sesion)
    assert (
        tipos.get("reserved_count"),
        tipos.get("available_spots"),
        tipos.get("is_reserved"),
    ) == (
        "integer",
        "integer",
        "boolean",
    )
    assert {"reserved_count", "available_spots", "is_reserved"} <= set(sesion["required"])

    pagina = _componente(esquema, _respuesta_200(esquema, "/me/registrations")["$ref"])
    inscripcion = _componente(esquema, pagina["properties"]["items"]["items"]["$ref"])
    reservadas = inscripcion["properties"].get("reserved_sessions", {})
    assert reservadas.get("type") == "array"
    assert "reserved_sessions" in inscripcion["required"]
    una = _componente(esquema, reservadas["items"]["$ref"])
    assert _tipos(una) == {
        "id": "string",
        "title": "string",
        "start_at": "string",
        "end_at": "string",
        "room": ["null", "string"],
    }
    assert sorted(una["required"]) == sorted(una["properties"])

    estadisticas = _componente(
        esquema, _respuesta_200(esquema, "/events/{id_evento}/stats")["$ref"]
    )
    por_sesion = estadisticas["properties"].get("sessions", {})
    assert por_sesion.get("type") == "array"
    assert "sessions" in estadisticas["required"]
    ocupacion = _componente(esquema, por_sesion["items"]["$ref"])
    assert _tipos(ocupacion) == {
        "id": "string",
        "title": "string",
        "reserved": "integer",
        "capacity": "integer",
        "occupancy_pct": "number",
    }
    assert sorted(ocupacion["required"]) == sorted(ocupacion["properties"])
