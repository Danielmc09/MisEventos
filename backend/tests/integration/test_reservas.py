"""Reservas de sesiones contra PostgreSQL: reservar con sus reglas, los cruces dentro del evento,
cancelar la reserva y la cascada desde la inscripción."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.test_eventos import auth, usuario_con_rol
from tests.integration.test_sesiones import crear_evento, utc

pytestmark = pytest.mark.integration


@pytest.fixture
def prefijo() -> str:
    return "rs" + uuid4().hex[:8]


@pytest.fixture
def usuarios(cliente_db, conexion, prefijo) -> dict[str, str]:
    """Token de cada usuario del test, por nombre."""
    roles = {"orga": "ORGANIZER", "ana": "ATTENDEE", "beto": "ATTENDEE"}
    return {
        nombre: usuario_con_rol(cliente_db, conexion, f"{prefijo}{nombre}@mail.com", rol)
        for nombre, rol in roles.items()
    }


def crear_sesion(
    cliente, token: str, evento: dict, inicio: str = "10:00", fin: str = "11:00", **cambios
) -> dict:
    cuerpo = {"title": "Testing en Python", "start_at": utc(inicio), "end_at": utc(fin)} | cambios
    respuesta = cliente.post(f"/events/{evento['id']}/sessions", json=cuerpo, headers=auth(token))
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def inscribirse(cliente, token: str, evento: dict) -> None:
    respuesta = cliente.post(f"/events/{evento['id']}/registrations", headers=auth(token))
    assert respuesta.status_code == 201, respuesta.text


def cancelar_inscripcion(cliente, token: str, evento: dict):
    return cliente.delete(f"/events/{evento['id']}/registrations/me", headers=auth(token))


def reservar(cliente, token: str | None, sesion: dict, **kwargs):
    return cliente.post(f"/sessions/{sesion['id']}/reservations", headers=auth(token), **kwargs)


def cancelar_reserva(cliente, token: str | None, sesion: dict):
    return cliente.delete(f"/sessions/{sesion['id']}/reservations/me", headers=auth(token))


def reservadas(conexion, sesion: dict) -> int:
    """Las reservas activas de la sesión, contadas en la base."""
    return conexion.execute(
        text(
            "SELECT count(*) FROM session_registrations WHERE session_id = :s AND status = 'ACTIVE'"
        ),
        {"s": sesion["id"]},
    ).scalar_one()


def reservas_de(conexion, email: str, sesion: dict) -> list[tuple]:
    """(status, cancelled_at) de cada reserva del usuario en la sesión, de la más vieja a la más
    nueva."""
    return [
        tuple(fila)
        for fila in conexion.execute(
            text(
                "SELECT r.status, r.cancelled_at FROM session_registrations r"
                " JOIN users u ON u.id = r.user_id"
                " WHERE r.session_id = :s AND u.email = :e ORDER BY r.created_at"
            ),
            {"s": sesion["id"], "e": email},
        ).all()
    ]


def empezar(conexion, sesion: dict) -> None:
    """La sesión empezó hace cinco minutos."""
    conexion.execute(
        text(
            "UPDATE sessions SET start_at = now() - interval '5 minutes',"
            " end_at = now() + interval '1 hour' WHERE id = :s"
        ),
        {"s": sesion["id"]},
    )


def assert_conflicto(respuesta, tipo: str) -> None:
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["type"] == tipo


@pytest.fixture
def evento(cliente_db, usuarios, prefijo) -> dict:
    return crear_evento(cliente_db, usuarios["orga"], f"{prefijo} PyCon")


# --- Reservar ------------------------------------------------------------------------------


def test_un_inscrito_reserva_una_sesion_con_lugar_y_la_base_cuenta_una_mas(
    cliente_db, conexion, usuarios, evento, prefijo
):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento, capacity=10)
    inscribirse(cliente_db, usuarios["ana"], evento)

    respuesta = reservar(cliente_db, usuarios["ana"], sesion)

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["session_id"], cuerpo["status"]) == (sesion["id"], "ACTIVE")
    assert cuerpo["created_at"].endswith("Z")
    assert reservadas(conexion, sesion) == 1
    assert reservas_de(conexion, f"{prefijo}ana@mail.com", sesion) == [("ACTIVE", None)]


def test_sin_inscripcion_activa_responde_not_registered(cliente_db, conexion, usuarios, evento):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento)

    respuesta = reservar(cliente_db, usuarios["ana"], sesion)

    assert_conflicto(respuesta, "not-registered")
    assert respuesta.json()["title"] == "Inscribite al evento para reservar sesiones"
    assert reservadas(conexion, sesion) == 0


def test_reservar_dos_veces_responde_already_reserved(cliente_db, conexion, usuarios, evento):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento)
    inscribirse(cliente_db, usuarios["ana"], evento)
    assert reservar(cliente_db, usuarios["ana"], sesion).status_code == 201

    assert_conflicto(reservar(cliente_db, usuarios["ana"], sesion), "already-reserved")
    assert reservadas(conexion, sesion) == 1


def test_una_sesion_llena_responde_session_full(cliente_db, conexion, usuarios, evento):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento, capacity=1)
    inscribirse(cliente_db, usuarios["ana"], evento)
    inscribirse(cliente_db, usuarios["beto"], evento)
    assert reservar(cliente_db, usuarios["ana"], sesion).status_code == 201

    assert_conflicto(reservar(cliente_db, usuarios["beto"], sesion), "session-full")
    assert reservadas(conexion, sesion) == 1


def test_una_sesion_sin_capacidad_propia_se_llena_con_la_del_evento(
    cliente_db, conexion, usuarios, prefijo
):
    evento = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} Taller")
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento)
    assert sesion["capacity"] is None
    inscribirse(cliente_db, usuarios["ana"], evento)
    inscribirse(cliente_db, usuarios["beto"], evento)
    assert reservar(cliente_db, usuarios["ana"], sesion).status_code == 201
    # El cupo del evento baja a 1 por SQL: por la API no se puede con dos inscritos, y así la
    # sesión, que usa la capacidad del evento, queda llena.
    conexion.execute(text("UPDATE events SET capacity = 1 WHERE id = :e"), {"e": evento["id"]})

    assert_conflicto(reservar(cliente_db, usuarios["beto"], sesion), "session-full")
    assert reservadas(conexion, sesion) == 1


def test_una_sesion_que_ya_empezo_responde_session_started(cliente_db, conexion, usuarios, evento):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento)
    inscribirse(cliente_db, usuarios["ana"], evento)
    empezar(conexion, sesion)

    assert_conflicto(reservar(cliente_db, usuarios["ana"], sesion), "session-started")
    assert reservadas(conexion, sesion) == 0


def test_una_sesion_de_un_borrador_responde_event_not_open_al_dueno_y_404_a_otro(
    cliente_db, conexion, usuarios, prefijo
):
    borrador = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} Borrador", publicar=False)
    sesion = crear_sesion(cliente_db, usuarios["orga"], borrador)

    assert_conflicto(reservar(cliente_db, usuarios["orga"], sesion), "event-not-open")
    ajeno = reservar(cliente_db, usuarios["ana"], sesion)
    assert ajeno.status_code == 404
    assert ajeno.json()["type"] == "not-found"
    assert reservadas(conexion, sesion) == 0


def test_una_sesion_de_un_evento_cancelado_responde_event_not_open(
    cliente_db, conexion, usuarios, evento
):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento)
    inscribirse(cliente_db, usuarios["ana"], evento)
    cancelado = cliente_db.post(f"/events/{evento['id']}/cancel", headers=auth(usuarios["orga"]))
    assert cancelado.status_code == 200, cancelado.text

    assert_conflicto(reservar(cliente_db, usuarios["ana"], sesion), "event-not-open")
    assert reservadas(conexion, sesion) == 0


def test_una_sesion_que_no_existe_responde_404(cliente_db, usuarios):
    respuesta = reservar(cliente_db, usuarios["ana"], {"id": str(uuid4())})

    assert respuesta.status_code == 404


def test_reservar_sin_token_responde_401(cliente_db, conexion, usuarios, evento):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento)

    assert reservar(cliente_db, None, sesion).status_code == 401
    assert reservadas(conexion, sesion) == 0


# --- Cruces --------------------------------------------------------------------------------


def test_una_sesion_que_se_cruza_con_otra_reserva_del_evento_responde_session_conflict(
    cliente_db, conexion, usuarios, evento
):
    reservada = crear_sesion(cliente_db, usuarios["orga"], evento, "10:00", "11:00", room="Sala C")
    paralela = crear_sesion(
        cliente_db, usuarios["orga"], evento, "10:30", "11:30", title="Django", room="Sala B"
    )
    inscribirse(cliente_db, usuarios["ana"], evento)
    assert reservar(cliente_db, usuarios["ana"], reservada).status_code == 201

    respuesta = reservar(cliente_db, usuarios["ana"], paralela)

    assert_conflicto(respuesta, "session-conflict")
    assert respuesta.json()["conflicts"] == [
        {
            "session_id": reservada["id"],
            "title": "Testing en Python",
            "start_at": utc("10:00"),
            "end_at": utc("11:00"),
            "room": "Sala C",
        }
    ]
    assert reservadas(conexion, paralela) == 0


def test_reservar_con_confirm_overlap_responde_422_y_no_crea_nada(
    cliente_db, conexion, usuarios, evento
):
    reservada = crear_sesion(cliente_db, usuarios["orga"], evento, "10:00", "11:00")
    paralela = crear_sesion(cliente_db, usuarios["orga"], evento, "10:00", "11:00")
    inscribirse(cliente_db, usuarios["ana"], evento)
    assert reservar(cliente_db, usuarios["ana"], reservada).status_code == 201

    respuesta = reservar(cliente_db, usuarios["ana"], paralela, json={"confirm_overlap": True})

    assert respuesta.status_code == 422, respuesta.text
    assert reservadas(conexion, paralela) == 0


def test_sesiones_que_se_tocan_se_reservan_las_dos(cliente_db, conexion, usuarios, evento):
    antes = crear_sesion(cliente_db, usuarios["orga"], evento, "09:00", "10:00")
    despues = crear_sesion(cliente_db, usuarios["orga"], evento, "10:00", "11:00")
    inscribirse(cliente_db, usuarios["ana"], evento)

    assert reservar(cliente_db, usuarios["ana"], antes).status_code == 201
    assert reservar(cliente_db, usuarios["ana"], despues).status_code == 201
    assert (reservadas(conexion, antes), reservadas(conexion, despues)) == (1, 1)


def test_una_sesion_que_se_cruza_con_una_reserva_de_otro_evento_se_reserva(
    cliente_db, conexion, usuarios, evento, prefijo
):
    otro = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} Python Day")
    de_otro = crear_sesion(cliente_db, usuarios["orga"], otro, "10:00", "11:00")
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento, "10:00", "11:00")
    inscribirse(cliente_db, usuarios["ana"], otro)
    inscribirse(cliente_db, usuarios["ana"], evento)
    assert reservar(cliente_db, usuarios["ana"], de_otro).status_code == 201

    respuesta = reservar(cliente_db, usuarios["ana"], sesion)

    assert respuesta.status_code == 201, respuesta.text
    assert reservadas(conexion, sesion) == 1


def test_una_sesion_llena_que_ademas_se_cruza_responde_session_full(
    cliente_db, conexion, usuarios, evento
):
    reservada = crear_sesion(cliente_db, usuarios["orga"], evento, "10:00", "11:00")
    llena = crear_sesion(cliente_db, usuarios["orga"], evento, "10:00", "11:00", capacity=1)
    inscribirse(cliente_db, usuarios["ana"], evento)
    inscribirse(cliente_db, usuarios["beto"], evento)
    assert reservar(cliente_db, usuarios["beto"], llena).status_code == 201
    assert reservar(cliente_db, usuarios["ana"], reservada).status_code == 201

    assert_conflicto(reservar(cliente_db, usuarios["ana"], llena), "session-full")
