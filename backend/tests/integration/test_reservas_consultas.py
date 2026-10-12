"""Las reservas en las consultas, contra PostgreSQL: el listado de sesiones de un evento, mis
inscripciones y las estadísticas del dueño."""

from uuid import uuid4

import pytest

from tests.integration.test_eventos import auth, usuario_con_rol
from tests.integration.test_inscripciones import contar_consultas
from tests.integration.test_reservas import (
    cancelar_reserva,
    crear_sesion,
    inscribirse,
    reservar,
)
from tests.integration.test_sesiones import crear_evento

pytestmark = pytest.mark.integration


@pytest.fixture
def prefijo() -> str:
    return "rc" + uuid4().hex[:8]


@pytest.fixture
def usuarios(cliente_db, conexion, prefijo) -> dict[str, str]:
    """Token de cada usuario del test, por nombre."""
    roles = {"orga": "ORGANIZER", "ana": "ATTENDEE", "beto": "ATTENDEE"}
    return {
        nombre: usuario_con_rol(cliente_db, conexion, f"{prefijo}{nombre}@mail.com", rol)
        for nombre, rol in roles.items()
    }


def reservar_ok(cliente, token: str, sesion: dict) -> None:
    respuesta = reservar(cliente, token, sesion)
    assert respuesta.status_code == 201, respuesta.text


def listado(cliente, evento: dict, token: str | None) -> dict[str, tuple]:
    """(reserved_count, available_spots, is_reserved) de cada sesión, por título."""
    respuesta = cliente.get(f"/events/{evento['id']}/sessions", headers=auth(token))
    assert respuesta.status_code == 200, respuesta.text
    return {
        s["title"]: (s["reserved_count"], s["available_spots"], s["is_reserved"])
        for s in respuesta.json()
    }


# --- El listado de sesiones -------------------------------------------------------------------


def test_el_listado_trae_reservadas_lugares_y_si_la_reserve_quien_pregunta(
    cliente_db, usuarios, prefijo
):
    # El evento tiene capacidad 100: la sesión sin capacidad propia usa esa.
    evento = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} PyCon")
    chica = crear_sesion(cliente_db, usuarios["orga"], evento, title="Chica", capacity=3)
    sin_capacidad = crear_sesion(
        cliente_db, usuarios["orga"], evento, "12:00", "13:00", title="Sin capacidad propia"
    )
    cancelada = crear_sesion(
        cliente_db, usuarios["orga"], evento, "14:00", "15:00", title="Cancelada", capacity=5
    )
    for nombre in ("ana", "beto"):
        inscribirse(cliente_db, usuarios[nombre], evento)
    reservar_ok(cliente_db, usuarios["ana"], chica)
    reservar_ok(cliente_db, usuarios["ana"], sin_capacidad)
    reservar_ok(cliente_db, usuarios["beto"], chica)
    reservar_ok(cliente_db, usuarios["beto"], cancelada)
    assert cancelar_reserva(cliente_db, usuarios["beto"], cancelada).status_code == 204

    assert listado(cliente_db, evento, usuarios["ana"]) == {
        "Chica": (2, 1, True),
        "Sin capacidad propia": (1, 99, True),
        "Cancelada": (0, 5, False),
    }
    assert listado(cliente_db, evento, usuarios["beto"]) == {
        "Chica": (2, 1, True),
        "Sin capacidad propia": (1, 99, False),
        "Cancelada": (0, 5, False),
    }
    assert listado(cliente_db, evento, None) == {
        "Chica": (2, 1, False),
        "Sin capacidad propia": (1, 99, False),
        "Cancelada": (0, 5, False),
    }


def test_el_listado_hace_las_mismas_consultas_con_2_sesiones_que_con_8(
    cliente_db, conexion, usuarios, prefijo
):
    def evento_con(cuantas: int) -> dict:
        evento = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} con {cuantas}")
        inscribirse(cliente_db, usuarios["ana"], evento)
        inscribirse(cliente_db, usuarios["beto"], evento)
        for numero in range(cuantas):
            sesion = crear_sesion(
                cliente_db,
                usuarios["orga"],
                evento,
                f"{9 + numero}:00",
                f"{10 + numero}:00",
                title=f"Sesión {numero}",
                capacity=10,
            )
            reservar_ok(cliente_db, usuarios["beto"], sesion)
            if numero % 2 == 0:
                reservar_ok(cliente_db, usuarios["ana"], sesion)
        return evento

    con_dos, con_ocho = evento_con(2), evento_con(8)

    def consultas(evento: dict, cuantas: int) -> int:
        with contar_consultas(conexion) as sentencias:
            sesiones = listado(cliente_db, evento, usuarios["ana"])
        # Las pares las reservaron Ana y Beto; las impares, solo Beto.
        assert sesiones == {
            f"Sesión {n}": (2, 8, True) if n % 2 == 0 else (1, 9, False) for n in range(cuantas)
        }
        return len(sentencias)

    assert consultas(con_dos, 2) == consultas(con_ocho, 8)


# --- Mis inscripciones ------------------------------------------------------------------------


def test_mis_inscripciones_trae_las_sesiones_reservadas_de_cada_una_por_hora(
    cliente_db, usuarios, prefijo
):
    evento = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} PyCon")
    otro = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} Python Day")
    sin_reservas = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} Sin reservas")
    tarde = crear_sesion(
        cliente_db, usuarios["orga"], evento, "15:00", "16:00", title="Tarde", room="Sala A"
    )
    manana = crear_sesion(cliente_db, usuarios["orga"], evento, "09:00", "10:00", title="Mañana")
    cancelada = crear_sesion(
        cliente_db, usuarios["orga"], evento, "11:00", "12:00", title="Cancelada"
    )
    de_beto = crear_sesion(cliente_db, usuarios["orga"], evento, "13:00", "14:00", title="De Beto")
    del_otro = crear_sesion(cliente_db, usuarios["orga"], otro, title="Del otro evento")
    for propio in (evento, otro, sin_reservas):
        inscribirse(cliente_db, usuarios["ana"], propio)
    inscribirse(cliente_db, usuarios["beto"], evento)
    for sesion in (tarde, manana, cancelada, del_otro):
        reservar_ok(cliente_db, usuarios["ana"], sesion)
    assert cancelar_reserva(cliente_db, usuarios["ana"], cancelada).status_code == 204
    reservar_ok(cliente_db, usuarios["beto"], de_beto)

    respuesta = cliente_db.get("/me/registrations", headers=auth(usuarios["ana"]))

    assert respuesta.status_code == 200, respuesta.text

    def resumen(sesion: dict) -> dict:
        return {k: sesion[k] for k in ("id", "title", "start_at", "end_at", "room")}

    por_evento = {i["event_id"]: i["reserved_sessions"] for i in respuesta.json()["items"]}
    assert por_evento == {
        evento["id"]: [resumen(manana), resumen(tarde)],
        otro["id"]: [resumen(del_otro)],
        sin_reservas["id"]: [],
    }


# --- Estadísticas del dueño -------------------------------------------------------------------


def test_las_estadisticas_del_dueno_traen_la_ocupacion_de_cada_sesion(
    cliente_db, usuarios, prefijo
):
    evento = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} PyCon")
    taller = crear_sesion(
        cliente_db, usuarios["orga"], evento, "15:00", "16:00", title="Taller", capacity=3
    )
    charla = crear_sesion(cliente_db, usuarios["orga"], evento, "09:00", "10:00", title="Charla")
    vacia = crear_sesion(
        cliente_db, usuarios["orga"], evento, "11:00", "12:00", title="Vacía", capacity=8
    )
    for nombre in ("ana", "beto"):
        inscribirse(cliente_db, usuarios[nombre], evento)
        reservar_ok(cliente_db, usuarios[nombre], charla)
    reservar_ok(cliente_db, usuarios["ana"], taller)
    reservar_ok(cliente_db, usuarios["beto"], taller)
    assert cancelar_reserva(cliente_db, usuarios["beto"], taller).status_code == 204

    respuesta = cliente_db.get(f"/events/{evento['id']}/stats", headers=auth(usuarios["orga"]))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["sessions"] == [
        {
            "id": charla["id"],
            "title": "Charla",
            "reserved": 2,
            "capacity": 100,
            "occupancy_pct": 2.0,
        },
        {"id": vacia["id"], "title": "Vacía", "reserved": 0, "capacity": 8, "occupancy_pct": 0.0},
        {
            "id": taller["id"],
            "title": "Taller",
            "reserved": 1,
            "capacity": 3,
            "occupancy_pct": 33.3,
        },
    ]
