"""Reservas simultáneas: el último lugar, las reservas propias que se cruzan, cancelar la
inscripción mientras se reserva y bajar la capacidad del evento mientras se reserva.

Corre fuera de la transacción del fixture (cada request hace commit de verdad), con datos propios
que se borran al final. Para que sea determinista, el test toma primero el bloqueo de la fila del
evento (el primero de la cadena evento → inscripción → sesión), espera a que todos los requests
estén frenados en ese bloqueo y recién ahí lo suelta: si el servicio no lo tomara, los requests no
esperarían y el test fallaría. Las conexiones de la app llevan `lock_timeout`: un bloqueo mutuo
termina en error y hace fallar el test en vez de colgarlo."""

import secrets
import threading
import time
from collections.abc import Callable
from functools import partial
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlmodel import Session

from app.core.config import Settings
from app.core.contrasenas import hashear
from app.core.tokens import crear_access_token
from app.main import create_app

pytestmark = pytest.mark.integration

SECRETO = "concurrencia-" + "x" * 32
ESPERA_MAXIMA = 30  # segundos que un hilo puede tardar antes de darlo por trabado


def esperar_frenados_en_el_evento(engine, cuantos: int, segundos: float = 15) -> None:
    """Hasta que `cuantos` conexiones esperan un bloqueo sobre events."""
    limite = time.monotonic() + segundos
    consulta = text(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
        " AND wait_event_type = 'Lock' AND query ILIKE '%FROM events%'"
    )
    while time.monotonic() < limite:
        with engine.connect() as conexion:
            if conexion.execute(consulta).scalar_one() >= cuantos:
                return
        time.sleep(0.05)
    pytest.fail(f"Los {cuantos} requests nunca esperaron el bloqueo del evento")


def insertar_usuario(conexion, email: str, rol: str) -> UUID:
    return conexion.execute(
        text("INSERT INTO users (email, password_hash, role) VALUES (:e, :h, :r) RETURNING id"),
        {"e": email, "h": hashear(secrets.token_urlsafe(16)), "r": rol},
    ).scalar_one()


def insertar_sesion(conexion, evento: UUID, inicio: str, fin: str, capacidad: int | None) -> UUID:
    return conexion.execute(
        text(
            "INSERT INTO sessions (event_id, title, start_at, end_at, capacity)"
            " VALUES (:e, 'Testing en Python', :i, :f, :c) RETURNING id"
        ),
        {"e": evento, "i": inicio, "f": fin, "c": capacidad},
    ).scalar_one()


@pytest.fixture
def datos(engine_de_test):
    """Un evento publicado con diez asistentes inscritos y tres sesiones: una con un solo lugar
    y dos que se cruzan entre sí. Con commit; se borran al terminar."""
    prefijo = "cr" + uuid4().hex[:8]
    with engine_de_test.begin() as conexion:
        organizador = insertar_usuario(conexion, f"{prefijo}orga@mail.com", "ORGANIZER")
        asistentes = [
            insertar_usuario(conexion, f"{prefijo}a{i}@mail.com", "ATTENDEE") for i in range(10)
        ]
        evento = conexion.execute(
            text(
                "INSERT INTO events (name, start_at, end_at, capacity, status, organizer_id)"
                " VALUES (:n, '2030-01-10T13:00:00Z', '2030-01-10T23:00:00Z', 50, 'PUBLISHED',"
                " :o) RETURNING id"
            ),
            {"n": f"{prefijo} evento", "o": organizador},
        ).scalar_one()
        for asistente in asistentes:
            conexion.execute(
                text("INSERT INTO registrations (user_id, event_id) VALUES (:u, :e)"),
                {"u": asistente, "e": evento},
            )
        un_lugar = insertar_sesion(
            conexion, evento, "2030-01-10T14:00:00Z", "2030-01-10T15:00:00Z", 1
        )
        paralelas = [
            insertar_sesion(conexion, evento, "2030-01-10T16:00:00Z", "2030-01-10T17:00:00Z", 10),
            insertar_sesion(conexion, evento, "2030-01-10T16:30:00Z", "2030-01-10T17:30:00Z", 10),
        ]
    try:
        yield {
            "evento": evento,
            "asistentes": asistentes,
            "un_lugar": un_lugar,
            "paralelas": paralelas,
        }
    finally:
        with engine_de_test.begin() as conexion:
            # Las sesiones, sus reservas y las inscripciones se van en cascada con el evento.
            conexion.execute(text("DELETE FROM events WHERE id = :e"), {"e": evento})
            conexion.execute(
                text("DELETE FROM users WHERE id = ANY(:ids)"),
                {"ids": [organizador, *asistentes]},
            )


Pedido = Callable[[TestClient], object]


def a_la_vez(engine, url_db: str, id_evento: UUID, pedidos: list[Pedido]) -> list:
    """Corre cada pedido en su hilo, todos frenados en el bloqueo del evento hasta que se suelta.
    Devuelve las respuestas; falla si algún hilo quedó trabado."""
    settings = Settings(
        _env_file=None,
        DATABASE_URL=url_db,
        JWT_SECRET=SECRETO,
        CORS_ORIGINS="http://localhost:5173",
    )
    app = create_app(settings)
    # Un engine propio, con commit de verdad y un tope para esperar un bloqueo.
    engine_app = create_engine(url_db, connect_args={"options": "-c lock_timeout=10000"})
    app.state.sesiones = partial(Session, engine_app)
    respuestas: list = []
    barrera = threading.Barrier(len(pedidos))

    def correr(pedido: Pedido) -> None:
        cliente = TestClient(app)
        barrera.wait()
        respuestas.append(pedido(cliente))

    try:
        with engine.connect() as cerrojo:
            transaccion = cerrojo.begin()
            cerrojo.execute(
                text("SELECT id FROM events WHERE id = :e FOR UPDATE"), {"e": id_evento}
            )
            hilos = [threading.Thread(target=correr, args=(p,)) for p in pedidos]
            for hilo in hilos:
                hilo.start()
            try:
                esperar_frenados_en_el_evento(engine, len(pedidos))
            finally:
                transaccion.commit()  # suelta el evento: los requests compiten por él
            for hilo in hilos:
                hilo.join(timeout=ESPERA_MAXIMA)
            assert not any(h.is_alive() for h in hilos), "un request quedó trabado"
    finally:
        engine_app.dispose()
    return respuestas


def headers(id_usuario: UUID) -> dict:
    return {"Authorization": f"Bearer {crear_access_token(id_usuario, SECRETO, 5)}"}


def reservar(id_usuario: UUID, id_sesion: UUID) -> Pedido:
    return lambda cliente: cliente.post(
        f"/sessions/{id_sesion}/reservations", headers=headers(id_usuario)
    )


def cancelar_inscripcion(id_usuario: UUID, id_evento: UUID) -> Pedido:
    return lambda cliente: cliente.delete(
        f"/events/{id_evento}/registrations/me", headers=headers(id_usuario)
    )


def activas(engine, consulta: str, **parametros) -> int:
    with engine.connect() as conexion:
        return conexion.execute(text(consulta), parametros).scalar_one()


def test_diez_inscritos_a_la_vez_por_el_unico_lugar_reserva_uno_solo(engine_de_test, url_db, datos):
    pedidos = [reservar(a, datos["un_lugar"]) for a in datos["asistentes"]]

    respuestas = a_la_vez(engine_de_test, url_db, datos["evento"], pedidos)

    assert len(respuestas) == 10
    assert sorted(r.status_code for r in respuestas) == [201] + [409] * 9
    assert all(r.json()["type"] == "session-full" for r in respuestas if r.status_code == 409)
    consulta = (
        "SELECT count(*) FROM session_registrations WHERE session_id = :s AND status = 'ACTIVE'"
    )
    assert activas(engine_de_test, consulta, s=datos["un_lugar"]) == 1


def test_la_misma_persona_a_la_vez_en_dos_sesiones_que_se_cruzan_reserva_una_sola(
    engine_de_test, url_db, datos
):
    ana = datos["asistentes"][0]
    pedidos = [reservar(ana, s) for s in datos["paralelas"]]

    respuestas = a_la_vez(engine_de_test, url_db, datos["evento"], pedidos)

    assert sorted(r.status_code for r in respuestas) == [201, 409]
    [rechazada] = [r for r in respuestas if r.status_code == 409]
    assert rechazada.json()["type"] == "session-conflict"
    consulta = (
        "SELECT count(*) FROM session_registrations"
        " WHERE user_id = :u AND session_id = ANY(:s) AND status = 'ACTIVE'"
    )
    assert activas(engine_de_test, consulta, u=ana, s=datos["paralelas"]) == 1


def test_cancelar_la_inscripcion_mientras_se_reserva_no_deja_reservas_colgando(
    engine_de_test, url_db, datos
):
    # Cuál de los dos gana el evento no se controla: valen los dos órdenes, y en ninguno queda
    # una reserva activa con la inscripción cancelada.
    ana = datos["asistentes"][0]
    pedidos = [reservar(ana, datos["paralelas"][0]), cancelar_inscripcion(ana, datos["evento"])]

    respuestas = a_la_vez(engine_de_test, url_db, datos["evento"], pedidos)

    estados = sorted(r.status_code for r in respuestas)
    assert estados in ([201, 204], [204, 409]), [r.text for r in respuestas]
    for rechazada in (r for r in respuestas if r.status_code == 409):
        assert rechazada.json()["type"] == "not-registered"
    inscripcion = (
        "SELECT count(*) FROM registrations"
        " WHERE user_id = :u AND event_id = :e AND status = 'ACTIVE'"
    )
    assert activas(engine_de_test, inscripcion, u=ana, e=datos["evento"]) == 0
    colgando = (
        "SELECT count(*) FROM session_registrations r JOIN sessions s ON s.id = r.session_id"
        " WHERE r.user_id = :u AND s.event_id = :e AND r.status = 'ACTIVE'"
    )
    assert activas(engine_de_test, colgando, u=ana, e=datos["evento"]) == 0


@pytest.fixture
def sin_capacidad_propia(engine_de_test):
    """Un evento publicado de capacidad 50 con tres inscritos y una sesión sin capacidad propia
    (usa la del evento) en la que dos de ellos ya reservaron. Con commit; se borra al terminar."""
    prefijo = "cc" + uuid4().hex[:8]
    with engine_de_test.begin() as conexion:
        organizador = insertar_usuario(conexion, f"{prefijo}orga@mail.com", "ORGANIZER")
        asistentes = [
            insertar_usuario(conexion, f"{prefijo}a{i}@mail.com", "ATTENDEE") for i in range(3)
        ]
        evento = conexion.execute(
            text(
                "INSERT INTO events (name, start_at, end_at, capacity, status, organizer_id)"
                " VALUES (:n, '2030-01-10T13:00:00Z', '2030-01-10T23:00:00Z', 50, 'PUBLISHED',"
                " :o) RETURNING id"
            ),
            {"n": f"{prefijo} evento", "o": organizador},
        ).scalar_one()
        for asistente in asistentes:
            conexion.execute(
                text("INSERT INTO registrations (user_id, event_id) VALUES (:u, :e)"),
                {"u": asistente, "e": evento},
            )
        sesion = insertar_sesion(
            conexion, evento, "2030-01-10T14:00:00Z", "2030-01-10T15:00:00Z", None
        )
        for asistente in asistentes[:2]:
            conexion.execute(
                text("INSERT INTO session_registrations (user_id, session_id) VALUES (:u, :s)"),
                {"u": asistente, "s": sesion},
            )
    try:
        yield {
            "evento": evento,
            "organizador": organizador,
            "asistentes": asistentes,
            "sesion": sesion,
        }
    finally:
        with engine_de_test.begin() as conexion:
            conexion.execute(text("DELETE FROM events WHERE id = :e"), {"e": evento})
            conexion.execute(
                text("DELETE FROM users WHERE id = ANY(:ids)"),
                {"ids": [organizador, *asistentes]},
            )


def cambiar_capacidad(id_usuario: UUID, id_evento: UUID, capacidad: int) -> Pedido:
    return lambda cliente: cliente.patch(
        f"/events/{id_evento}", json={"capacity": capacidad}, headers=headers(id_usuario)
    )


@pytest.mark.parametrize("capacidad", [2, 3], ids=["por-debajo", "justa"])
def test_bajar_la_capacidad_del_evento_mientras_se_reserva_deja_la_base_consistente(
    engine_de_test, url_db, sin_capacidad_propia, capacidad
):
    # Los dos toman primero el evento, así que se ordenan ahí y ninguno espera al otro en
    # círculo. Cuál gana no se controla: en cualquier orden, la sesión nunca termina con más
    # reservas activas que la capacidad efectiva final, que es la del evento.
    datos = sin_capacidad_propia
    pedidos = [
        reservar(datos["asistentes"][2], datos["sesion"]),
        cambiar_capacidad(datos["organizador"], datos["evento"], capacidad),
    ]

    respuestas = a_la_vez(engine_de_test, url_db, datos["evento"], pedidos)

    reserva, cambio = respuestas if respuestas[0].request.method == "POST" else respuestas[::-1]
    assert reserva.status_code == 201, reserva.text
    if capacidad == 2:
        assert cambio.status_code == 409, cambio.text
        assert cambio.json()["type"] in {
            "capacity-below-reservations",
            "capacity-below-registrations",
        }
    else:
        assert cambio.status_code == 200, cambio.text
    final = activas(engine_de_test, "SELECT capacity FROM events WHERE id = :e", e=datos["evento"])
    reservas = activas(
        engine_de_test,
        "SELECT count(*) FROM session_registrations WHERE session_id = :s AND status = 'ACTIVE'",
        s=datos["sesion"],
    )
    assert reservas == 3
    assert reservas <= final
