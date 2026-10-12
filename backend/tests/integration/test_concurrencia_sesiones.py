"""Dos requests a la vez que asignan al mismo ponente en horarios que se cruzan: pasa uno solo.

Corre fuera de la transacción del fixture (cada request hace commit de verdad), con datos propios
que se borran al final. Para que sea determinista, el test toma primero el bloqueo del ponente,
espera a que los dos requests estén frenados en ese bloqueo y recién ahí lo suelta: si el
servicio no bloqueara al ponente, los dos pasarían sin esperar y el test fallaría."""

import secrets
import threading
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings
from app.core.contrasenas import hashear
from app.core.tokens import crear_access_token
from app.main import create_app

pytestmark = pytest.mark.integration

SECRETO = "concurrencia-" + "x" * 32


def esperar_frenados_en_ponentes(engine, cuantos: int, segundos: float = 15) -> None:
    """Hasta que `cuantos` conexiones esperan un bloqueo sobre speakers."""
    limite = time.monotonic() + segundos
    consulta = text(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
        " AND wait_event_type = 'Lock' AND query ILIKE '%FROM speakers%'"
    )
    while time.monotonic() < limite:
        with engine.connect() as conexion:
            if conexion.execute(consulta).scalar_one() >= cuantos:
                return
        time.sleep(0.05)
    pytest.fail(f"Los {cuantos} requests nunca esperaron el bloqueo del ponente")


@pytest.fixture
def datos(engine_de_test):
    """Un organizador, dos eventos suyos y un ponente, con commit. Se borran al terminar."""
    prefijo = "cc" + uuid4().hex[:8]
    with engine_de_test.begin() as conexion:
        id_usuario = conexion.execute(
            text(
                "INSERT INTO users (email, password_hash, role) VALUES (:e, :h, 'ORGANIZER')"
                " RETURNING id"
            ),
            {"e": f"{prefijo}@mail.com", "h": hashear(secrets.token_urlsafe(16))},
        ).scalar_one()
        ids_evento = [
            conexion.execute(
                text(
                    "INSERT INTO events (name, start_at, end_at, capacity, status, organizer_id)"
                    " VALUES (:n, '2030-01-10T13:00:00Z', '2030-01-10T23:00:00Z', 100,"
                    " 'PUBLISHED', :o) RETURNING id"
                ),
                {"n": f"{prefijo} evento {i}", "o": id_usuario},
            ).scalar_one()
            for i in range(2)
        ]
        id_ponente = conexion.execute(
            text("INSERT INTO speakers (full_name, created_by) VALUES (:n, :o) RETURNING id"),
            {"n": f"{prefijo} Ana Pérez", "o": id_usuario},
        ).scalar_one()
    try:
        yield {"usuario": id_usuario, "eventos": ids_evento, "ponente": id_ponente}
    finally:
        with engine_de_test.begin() as conexion:
            # Las sesiones y sus vínculos se van en cascada con los eventos.
            conexion.execute(text("DELETE FROM events WHERE organizer_id = :o"), {"o": id_usuario})
            conexion.execute(text("DELETE FROM speakers WHERE id = :p"), {"p": id_ponente})
            conexion.execute(text("DELETE FROM users WHERE id = :o"), {"o": id_usuario})


def test_dos_requests_simultaneos_con_el_mismo_ponente_dan_un_201_y_un_409(
    engine_de_test, url_db, datos
):
    settings = Settings(
        _env_file=None,
        DATABASE_URL=url_db,
        JWT_SECRET=SECRETO,
        CORS_ORIGINS="http://localhost:5173",
    )
    app = create_app(settings)  # con su propio engine: cada request hace commit de verdad
    token = crear_access_token(datos["usuario"], SECRETO, 5)
    cuerpo = {
        "title": "Testing en Python",
        "start_at": "2030-01-10T15:00:00Z",
        "end_at": "2030-01-10T16:00:00Z",
        "speaker_ids": [str(datos["ponente"])],
    }
    estados: list[int] = []
    barrera = threading.Barrier(2)

    def pedir(id_evento) -> None:
        cliente = TestClient(app)
        barrera.wait()
        respuesta = cliente.post(
            f"/events/{id_evento}/sessions",
            json=cuerpo,
            headers={"Authorization": f"Bearer {token}"},
        )
        estados.append(respuesta.status_code)

    try:
        with engine_de_test.connect() as cerrojo:
            transaccion = cerrojo.begin()
            cerrojo.execute(
                text("SELECT id FROM speakers WHERE id = :p FOR UPDATE"), {"p": datos["ponente"]}
            )
            hilos = [threading.Thread(target=pedir, args=(e,)) for e in datos["eventos"]]
            for hilo in hilos:
                hilo.start()
            try:
                esperar_frenados_en_ponentes(engine_de_test, 2)
            finally:
                transaccion.commit()  # suelta el ponente: los dos requests compiten por él
            for hilo in hilos:
                hilo.join(timeout=30)
    finally:
        app.state.sesiones.args[0].dispose()

    assert sorted(estados) == [201, 409]
    with engine_de_test.connect() as conexion:
        vinculos = conexion.execute(
            text("SELECT count(*) FROM session_speakers WHERE speaker_id = :p"),
            {"p": datos["ponente"]},
        ).scalar_one()
    assert vinculos == 1
