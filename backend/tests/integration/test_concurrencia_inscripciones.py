"""Inscripciones simultáneas al mismo evento: el cupo y la inscripción única se respetan.

Corre fuera de la transacción del fixture (cada request hace commit de verdad), con datos propios
que se borran al final. Para que sea determinista, el test toma primero el bloqueo de la fila del
evento, espera a que todos los requests estén frenados en ese bloqueo y recién ahí lo suelta: si el
servicio no bloqueara el evento, los requests no esperarían y el test fallaría."""

import secrets
import threading
import time
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.core.contrasenas import hashear
from app.core.tokens import crear_access_token
from app.main import create_app

pytestmark = pytest.mark.integration

SECRETO = "concurrencia-" + "x" * 32


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


@pytest.fixture
def datos(engine_de_test):
    """Un organizador, un evento publicado con capacidad 1 y diez asistentes, con commit. Se
    borran al terminar."""
    prefijo = "ci" + uuid4().hex[:8]
    with engine_de_test.begin() as conexion:
        organizador = insertar_usuario(conexion, f"{prefijo}orga@mail.com", "ORGANIZER")
        asistentes = [
            insertar_usuario(conexion, f"{prefijo}a{i}@mail.com", "ATTENDEE") for i in range(10)
        ]
        evento = conexion.execute(
            text(
                "INSERT INTO events (name, start_at, end_at, capacity, status, organizer_id)"
                " VALUES (:n, '2030-01-10T13:00:00Z', '2030-01-10T23:00:00Z', 1, 'PUBLISHED',"
                " :o) RETURNING id"
            ),
            {"n": f"{prefijo} evento", "o": organizador},
        ).scalar_one()
    try:
        yield {"evento": evento, "asistentes": asistentes}
    finally:
        with engine_de_test.begin() as conexion:
            # Las inscripciones se van en cascada con el evento.
            conexion.execute(text("DELETE FROM events WHERE id = :e"), {"e": evento})
            conexion.execute(
                text("DELETE FROM users WHERE id = ANY(:ids)"),
                {"ids": [organizador, *asistentes]},
            )


def inscribir_a_la_vez(engine, url_db: str, id_evento: UUID, ids_usuario: list[UUID]) -> list:
    """Un request por usuario, todos frenados en el bloqueo del evento hasta que se suelta.
    Devuelve las respuestas."""
    settings = Settings(
        _env_file=None,
        DATABASE_URL=url_db,
        JWT_SECRET=SECRETO,
        CORS_ORIGINS="http://localhost:5173",
    )
    app = create_app(settings)  # con su propio engine: cada request hace commit de verdad
    respuestas: list = []
    barrera = threading.Barrier(len(ids_usuario))

    def pedir(id_usuario: UUID) -> None:
        token = crear_access_token(id_usuario, SECRETO, 5)
        cliente = TestClient(app)
        barrera.wait()
        respuestas.append(
            cliente.post(
                f"/events/{id_evento}/registrations",
                headers={"Authorization": f"Bearer {token}"},
            )
        )

    try:
        with engine.connect() as cerrojo:
            transaccion = cerrojo.begin()
            cerrojo.execute(
                text("SELECT id FROM events WHERE id = :e FOR UPDATE"), {"e": id_evento}
            )
            hilos = [threading.Thread(target=pedir, args=(u,)) for u in ids_usuario]
            for hilo in hilos:
                hilo.start()
            try:
                esperar_frenados_en_el_evento(engine, len(ids_usuario))
            finally:
                transaccion.commit()  # suelta el evento: los requests compiten por él
            for hilo in hilos:
                hilo.join(timeout=30)
    finally:
        app.state.sesiones.args[0].dispose()
    return respuestas


def activas(engine, id_evento: UUID) -> int:
    with engine.connect() as conexion:
        return conexion.execute(
            text("SELECT count(*) FROM registrations WHERE event_id = :e AND status = 'ACTIVE'"),
            {"e": id_evento},
        ).scalar_one()


def test_diez_personas_a_la_vez_por_el_ultimo_cupo_entra_una_sola(engine_de_test, url_db, datos):
    respuestas = inscribir_a_la_vez(engine_de_test, url_db, datos["evento"], datos["asistentes"])

    assert len(respuestas) == 10
    assert sorted(r.status_code for r in respuestas) == [201] + [409] * 9
    assert all(r.json()["type"] == "capacity-full" for r in respuestas if r.status_code == 409)
    assert activas(engine_de_test, datos["evento"]) == 1


def test_la_misma_persona_dos_veces_a_la_vez_queda_inscrita_una_sola_vez(
    engine_de_test, url_db, datos
):
    ana = datos["asistentes"][0]

    respuestas = inscribir_a_la_vez(engine_de_test, url_db, datos["evento"], [ana, ana])

    assert sorted(r.status_code for r in respuestas) == [201, 409]
    [rechazada] = [r for r in respuestas if r.status_code == 409]
    assert rechazada.json()["type"] == "already-registered"
    assert activas(engine_de_test, datos["evento"]) == 1
