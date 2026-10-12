"""Inscripciones contra PostgreSQL: inscribirse con sus reglas, cancelar y volver a inscribirse."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.test_eventos import auth, cuerpo_valido, usuario_con_rol

pytestmark = pytest.mark.integration


@pytest.fixture
def prefijo() -> str:
    return "in" + uuid4().hex[:8]


@pytest.fixture
def usuarios(cliente_db, conexion, prefijo) -> dict[str, str]:
    """Token de cada usuario del test, por nombre."""
    roles = {"orga": "ORGANIZER", "ana": "ATTENDEE", "beto": "ATTENDEE"}
    return {
        nombre: usuario_con_rol(cliente_db, conexion, f"{prefijo}{nombre}@mail.com", rol)
        for nombre, rol in roles.items()
    }


def crear_evento(cliente, token: str, *, capacidad: int = 10, publicar: bool = True) -> str:
    cuerpo = cuerpo_valido() | {"capacity": capacidad}
    creado = cliente.post("/events", json=cuerpo, headers=auth(token))
    assert creado.status_code == 201, creado.text
    id_evento = creado.json()["id"]
    if publicar:
        publicado = cliente.post(f"/events/{id_evento}/publish", headers=auth(token))
        assert publicado.status_code == 200, publicado.text
    return id_evento


def inscribirse(cliente, token: str | None, id_evento: str):
    return cliente.post(f"/events/{id_evento}/registrations", headers=auth(token))


def cancelar(cliente, token: str | None, id_evento: str):
    return cliente.delete(f"/events/{id_evento}/registrations/me", headers=auth(token))


def empezar(conexion, id_evento: str) -> None:
    """Lo corre una hora hacia atrás: empezó hace una hora y sigue en curso."""
    conexion.execute(
        text(
            "UPDATE events SET start_at = now() - interval '1 hour',"
            " end_at = now() + interval '7 hours' WHERE id = :id"
        ),
        {"id": id_evento},
    )


def inscripciones(conexion, id_evento: str, email: str | None = None) -> list[tuple]:
    """(status, cancelled_at) de cada inscripción del evento, o solo las de ese usuario."""
    consulta = (
        "SELECT r.status, r.cancelled_at FROM registrations r JOIN users u ON u.id = r.user_id"
        " WHERE r.event_id = :e AND (CAST(:email AS text) IS NULL OR u.email = :email)"
        " ORDER BY r.created_at"
    )
    return [
        tuple(fila)
        for fila in conexion.execute(text(consulta), {"e": id_evento, "email": email}).all()
    ]


def assert_conflicto(respuesta, tipo: str) -> None:
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["type"] == tipo


# --- Inscribirse ---------------------------------------------------------------------------


def test_inscribirse_responde_201_y_el_evento_cuenta_un_inscrito_mas(
    cliente_db, conexion, usuarios, prefijo
):
    id_evento = crear_evento(cliente_db, usuarios["orga"], capacidad=10)

    respuesta = inscribirse(cliente_db, usuarios["ana"], id_evento)

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["event_id"], cuerpo["status"]) == (id_evento, "ACTIVE")
    assert inscripciones(conexion, id_evento, f"{prefijo}ana@mail.com") == [("ACTIVE", None)]
    detalle = cliente_db.get(f"/events/{id_evento}").json()
    assert (detalle["registered_count"], detalle["available_spots"]) == (1, 9)


def test_un_borrador_responde_event_not_open_y_uno_ajeno_404(cliente_db, conexion, usuarios):
    borrador = crear_evento(cliente_db, usuarios["orga"], publicar=False)

    assert_conflicto(inscribirse(cliente_db, usuarios["orga"], borrador), "event-not-open")
    ajeno = inscribirse(cliente_db, usuarios["ana"], borrador)
    assert ajeno.status_code == 404
    assert ajeno.json()["type"] == "not-found"
    assert inscripciones(conexion, borrador) == []


def test_un_evento_cancelado_responde_event_not_open(cliente_db, conexion, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    cancelado = cliente_db.post(f"/events/{id_evento}/cancel", headers=auth(usuarios["orga"]))
    assert cancelado.status_code == 200, cancelado.text

    assert_conflicto(inscribirse(cliente_db, usuarios["ana"], id_evento), "event-not-open")
    assert inscripciones(conexion, id_evento) == []


def test_un_evento_que_ya_empezo_responde_event_started(cliente_db, conexion, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    empezar(conexion, id_evento)

    assert_conflicto(inscribirse(cliente_db, usuarios["ana"], id_evento), "event-started")
    assert inscripciones(conexion, id_evento) == []


def test_inscribirse_dos_veces_responde_already_registered(cliente_db, conexion, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201

    assert_conflicto(inscribirse(cliente_db, usuarios["ana"], id_evento), "already-registered")
    assert inscripciones(conexion, id_evento) == [("ACTIVE", None)]


def test_un_evento_lleno_responde_capacity_full(cliente_db, conexion, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"], capacidad=1)
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201

    respuesta = inscribirse(cliente_db, usuarios["beto"], id_evento)

    assert_conflicto(respuesta, "capacity-full")
    assert respuesta.json()["title"] == "El evento no tiene cupos"
    assert len(inscripciones(conexion, id_evento)) == 1


def test_sin_token_responde_401(cliente_db, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"])

    assert inscribirse(cliente_db, None, id_evento).status_code == 401


def test_el_dueno_puede_inscribirse_a_su_propio_evento(cliente_db, conexion, usuarios, prefijo):
    id_evento = crear_evento(cliente_db, usuarios["orga"])

    assert inscribirse(cliente_db, usuarios["orga"], id_evento).status_code == 201
    assert inscripciones(conexion, id_evento, f"{prefijo}orga@mail.com") == [("ACTIVE", None)]
