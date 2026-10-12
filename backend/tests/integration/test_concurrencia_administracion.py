"""Dos admins, los únicos, se degradan mutuamente a la vez: siempre queda un admin activo.

Corre fuera de la transacción del fixture (cada request hace commit de verdad), con datos propios
que se borran al final. Para que sea determinista, el test toma primero el bloqueo de las filas
de los dos admins, espera a que los dos requests estén frenados en ese bloqueo y recién ahí lo
suelta: si el servicio no bloqueara a los admins antes de contarlos, los requests no esperarían y
el test fallaría. Si la base de test tuviera otros admins activos, se desactivan mientras corre
el test y se restauran al final."""

import secrets
import threading
import time
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


def esperar_frenados_en_usuarios(engine, cuantos: int, segundos: float = 15) -> None:
    """Hasta que `cuantos` conexiones esperan un bloqueo sobre users."""
    limite = time.monotonic() + segundos
    consulta = text(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
        " AND wait_event_type = 'Lock' AND query ILIKE '%FROM users%'"
    )
    while time.monotonic() < limite:
        with engine.connect() as conexion:
            if conexion.execute(consulta).scalar_one() >= cuantos:
                return
        time.sleep(0.05)
    pytest.fail(f"Los {cuantos} requests nunca esperaron el bloqueo de los admins")


def insertar_admin(conexion, email: str) -> UUID:
    return conexion.execute(
        text(
            "INSERT INTO users (email, password_hash, role) VALUES (:e, :h, 'ADMIN') RETURNING id"
        ),
        {"e": email, "h": hashear(secrets.token_urlsafe(16))},
    ).scalar_one()


def admins_activos(engine, ids: list[UUID] | None = None) -> list[UUID]:
    consulta = "SELECT id FROM users WHERE role = 'ADMIN' AND is_active"
    with engine.connect() as conexion:
        if ids is None:
            return list(conexion.execute(text(consulta)).scalars())
        return list(
            conexion.execute(text(consulta + " AND id = ANY(:ids)"), {"ids": ids}).scalars()
        )


@pytest.fixture
def dos_admins(engine_de_test):
    """Dos admins con commit, los únicos activos de la base mientras dura el test."""
    prefijo = "ca" + uuid4().hex[:8]
    with engine_de_test.begin() as conexion:
        apartados = list(
            conexion.execute(
                text(
                    "UPDATE users SET is_active = false WHERE role = 'ADMIN' AND is_active"
                    " RETURNING id"
                )
            ).scalars()
        )
        admins = [insertar_admin(conexion, f"{prefijo}admin{i}@mail.com") for i in range(2)]
    try:
        yield admins
    finally:
        with engine_de_test.begin() as conexion:
            conexion.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": admins})
            if apartados:
                conexion.execute(
                    text("UPDATE users SET is_active = true WHERE id = ANY(:ids)"),
                    {"ids": apartados},
                )


def degradarse_a_la_vez(engine, url_db: str, pedidos: list[tuple[UUID, UUID]]) -> list:
    """Cada `(actor, objetivo)` en su hilo, todos frenados en el bloqueo de los admins hasta que
    se suelta. Devuelve las respuestas; falla si algún hilo quedó trabado."""
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

    def correr(actor: UUID, objetivo: UUID) -> None:
        cliente = TestClient(app)
        token = crear_access_token(actor, SECRETO, 5)
        barrera.wait()
        respuestas.append(
            cliente.patch(
                f"/admin/users/{objetivo}",
                json={"role": "ATTENDEE"},
                headers={"Authorization": f"Bearer {token}"},
            )
        )

    ids = sorted({id_ for pedido in pedidos for id_ in pedido})
    try:
        with engine.connect() as cerrojo:
            transaccion = cerrojo.begin()
            cerrojo.execute(
                text("SELECT id FROM users WHERE id = ANY(:ids) ORDER BY id FOR UPDATE"),
                {"ids": ids},
            )
            hilos = [threading.Thread(target=correr, args=p) for p in pedidos]
            for hilo in hilos:
                hilo.start()
            try:
                esperar_frenados_en_usuarios(engine, len(pedidos))
            finally:
                transaccion.commit()  # suelta a los admins: los requests compiten por ellos
            for hilo in hilos:
                hilo.join(timeout=ESPERA_MAXIMA)
            assert not any(h.is_alive() for h in hilos), "un request quedó trabado"
    finally:
        engine_app.dispose()
    return respuestas


def test_dos_admins_que_se_degradan_a_la_vez_dejan_exactamente_un_admin_activo(
    engine_de_test, url_db, dos_admins
):
    uno, otro = dos_admins

    respuestas = degradarse_a_la_vez(engine_de_test, url_db, [(uno, otro), (otro, uno)])

    assert sorted(r.status_code for r in respuestas) == [200, 409], [r.text for r in respuestas]
    [rechazada] = [r for r in respuestas if r.status_code == 409]
    assert rechazada.json()["type"] == "last-admin"
    assert rechazada.json()["title"] == "Tiene que quedar al menos un administrador activo"
    assert len(admins_activos(engine_de_test, dos_admins)) == 1
    assert len(admins_activos(engine_de_test)) == 1
