"""Una sesión con reservas activas contra PostgreSQL: no cambia de horario, no se elimina y su
capacidad no baja de lo reservado; el evento tampoco baja la suya por debajo de las reservas de una
sesión sin capacidad propia. Las reservas canceladas no cuentan."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.test_eventos import auth, usuario_con_rol
from tests.integration.test_reservas import (
    assert_conflicto,
    cancelar_inscripcion,
    cancelar_reserva,
    crear_sesion,
    inscribirse,
    reservadas,
    reservar,
)
from tests.integration.test_sesiones import crear_evento, utc

pytestmark = pytest.mark.integration


@pytest.fixture
def prefijo() -> str:
    return "sr" + uuid4().hex[:8]


@pytest.fixture
def usuarios(cliente_db, conexion, prefijo) -> dict[str, str]:
    """Token de cada usuario del test, por nombre."""
    roles = {"orga": "ORGANIZER", "ana": "ATTENDEE", "beto": "ATTENDEE"}
    return {
        nombre: usuario_con_rol(cliente_db, conexion, f"{prefijo}{nombre}@mail.com", rol)
        for nombre, rol in roles.items()
    }


@pytest.fixture
def evento(cliente_db, usuarios, prefijo) -> dict:
    """Publicado, con capacidad 100."""
    return crear_evento(cliente_db, usuarios["orga"], f"{prefijo} PyCon")


def con_reservas(cliente, usuarios: dict, evento: dict, sesion: dict, *quienes: str) -> None:
    for nombre in quienes:
        inscribirse(cliente, usuarios[nombre], evento)
        assert reservar(cliente, usuarios[nombre], sesion).status_code == 201


def editar_sesion(cliente, token: str, sesion: dict, datos: dict):
    return cliente.patch(f"/sessions/{sesion['id']}", json=datos, headers=auth(token))


def editar_evento(cliente, token: str, evento: dict, datos: dict):
    return cliente.patch(f"/events/{evento['id']}", json=datos, headers=auth(token))


def en_la_base(conexion, sesion: dict) -> tuple | None:
    fila = conexion.execute(
        text("SELECT title, start_at, end_at, capacity FROM sessions WHERE id = :s"),
        {"s": sesion["id"]},
    ).first()
    return None if fila is None else tuple(fila)


def capacidad_del_evento(conexion, evento: dict) -> int:
    return conexion.execute(
        text("SELECT capacity FROM events WHERE id = :e"), {"e": evento["id"]}
    ).scalar_one()


# --- La sesión -----------------------------------------------------------------------------


def test_con_reservas_activas_el_horario_no_cambia_y_el_titulo_si(
    cliente_db, conexion, usuarios, evento
):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento, capacity=10)
    con_reservas(cliente_db, usuarios, evento, sesion, "ana")
    antes = en_la_base(conexion, sesion)

    for cambio in ({"start_at": utc("09:30")}, {"end_at": utc("11:30")}):
        respuesta = editar_sesion(cliente_db, usuarios["orga"], sesion, cambio)
        assert_conflicto(respuesta, "session-has-reservations")
    assert en_la_base(conexion, sesion) == antes

    respuesta = editar_sesion(cliente_db, usuarios["orga"], sesion, {"title": "Pytest avanzado"})

    assert respuesta.status_code == 200, respuesta.text
    assert en_la_base(conexion, sesion)[0] == "Pytest avanzado"


def test_con_reservas_activas_no_se_elimina(cliente_db, conexion, usuarios, evento):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento)
    con_reservas(cliente_db, usuarios, evento, sesion, "ana")

    respuesta = cliente_db.delete(f"/sessions/{sesion['id']}", headers=auth(usuarios["orga"]))

    assert_conflicto(respuesta, "session-has-reservations")
    assert en_la_base(conexion, sesion) is not None
    assert reservadas(conexion, sesion) == 1


def test_la_capacidad_de_la_sesion_no_baja_de_sus_reservas_activas(
    cliente_db, conexion, usuarios, evento
):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento, capacity=10)
    con_reservas(cliente_db, usuarios, evento, sesion, "ana", "beto")

    respuesta = editar_sesion(cliente_db, usuarios["orga"], sesion, {"capacity": 1})

    assert_conflicto(respuesta, "capacity-below-reservations")
    assert en_la_base(conexion, sesion)[3] == 10
    igual = editar_sesion(cliente_db, usuarios["orga"], sesion, {"capacity": 2})
    assert igual.status_code == 200, igual.text
    assert en_la_base(conexion, sesion)[3] == 2


def test_con_reservas_canceladas_la_sesion_se_mueve_achica_y_elimina(
    cliente_db, conexion, usuarios, evento
):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento, capacity=10)
    con_reservas(cliente_db, usuarios, evento, sesion, "ana", "beto")
    assert cancelar_reserva(cliente_db, usuarios["ana"], sesion).status_code == 204
    assert cancelar_inscripcion(cliente_db, usuarios["beto"], evento).status_code == 204
    assert reservadas(conexion, sesion) == 0

    movida = editar_sesion(cliente_db, usuarios["orga"], sesion, {"start_at": utc("09:30")})
    achicada = editar_sesion(cliente_db, usuarios["orga"], sesion, {"capacity": 1})
    eliminada = cliente_db.delete(f"/sessions/{sesion['id']}", headers=auth(usuarios["orga"]))

    assert movida.status_code == 200, movida.text
    assert achicada.status_code == 200, achicada.text
    assert eliminada.status_code == 204, eliminada.text
    assert en_la_base(conexion, sesion) is None


# --- El evento -----------------------------------------------------------------------------


def test_la_capacidad_del_evento_no_baja_de_las_reservas_de_una_sesion_sin_capacidad_propia(
    cliente_db, conexion, usuarios, evento
):
    sin_capacidad = crear_sesion(cliente_db, usuarios["orga"], evento)
    con_reservas(cliente_db, usuarios, evento, sin_capacidad, "ana", "beto")

    respuesta = editar_evento(cliente_db, usuarios["orga"], evento, {"capacity": 1})

    assert_conflicto(respuesta, "capacity-below-reservations")
    assert capacidad_del_evento(conexion, evento) == 100
    igual = editar_evento(cliente_db, usuarios["orga"], evento, {"capacity": 2})
    assert igual.status_code == 200, igual.text
    assert capacidad_del_evento(conexion, evento) == 2


def test_las_reservas_canceladas_no_frenan_bajar_la_capacidad_del_evento(
    cliente_db, conexion, usuarios, evento
):
    sesion = crear_sesion(cliente_db, usuarios["orga"], evento)
    con_reservas(cliente_db, usuarios, evento, sesion, "ana", "beto")
    # Beto cancela la inscripción y con ella su reserva: queda una activa y una cancelada.
    assert cancelar_inscripcion(cliente_db, usuarios["beto"], evento).status_code == 204

    respuesta = editar_evento(cliente_db, usuarios["orga"], evento, {"capacity": 1})

    assert respuesta.status_code == 200, respuesta.text
    assert capacidad_del_evento(conexion, evento) == 1
