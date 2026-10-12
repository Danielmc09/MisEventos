"""Cambios concurrentes entre admins: siempre queda un admin activo, quien perdió el permiso
mientras esperaba no lo sigue usando, y dos usuarios nunca terminan con el mismo email.

Corre fuera de la transacción del fixture (cada request hace commit de verdad), con datos propios
que se borran al final. Para que sea determinista, el test toma primero el bloqueo de las filas
involucradas, espera a que los requests estén frenados en ese bloqueo y recién ahí lo suelta. Si
el servicio contara a los admins sin bloquearlos, los requests igual esperarían al bloquear la
fila del usuario que cambian, pero cada uno habría contado dos admins antes de esperar: los dos
responderían 200 y el test fallaría. Si la base de test tuviera otros admins activos, se
desactivan mientras corre el test y se restauran al final."""

import secrets
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
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


def insertar_usuario(conexion, email: str, rol: str = "ADMIN") -> UUID:
    return conexion.execute(
        text(
            "INSERT INTO users (email, password_hash, role)"
            " VALUES (:e, :h, CAST(:r AS user_role)) RETURNING id"
        ),
        {"e": email, "h": hashear(secrets.token_urlsafe(16)), "r": rol},
    ).scalar_one()


def admins_activos(engine, ids: list[UUID] | None = None) -> list[UUID]:
    consulta = "SELECT id FROM users WHERE role = 'ADMIN' AND is_active"
    with engine.connect() as conexion:
        if ids is None:
            return list(conexion.execute(text(consulta)).scalars())
        return list(
            conexion.execute(text(consulta + " AND id = ANY(:ids)"), {"ids": ids}).scalars()
        )


@contextmanager
def solo_estos_usuarios(engine, roles: list[str]) -> Iterator[list[UUID]]:
    """Usuarios con commit, uno por rol; sus admins son los únicos activos mientras dura."""
    prefijo = "ca" + uuid4().hex[:8]
    with engine.begin() as conexion:
        apartados = list(
            conexion.execute(
                text(
                    "UPDATE users SET is_active = false WHERE role = 'ADMIN' AND is_active"
                    " RETURNING id"
                )
            ).scalars()
        )
        ids = [
            insertar_usuario(conexion, f"{prefijo}usuario{i}@mail.com", rol)
            for i, rol in enumerate(roles)
        ]
    try:
        yield ids
    finally:
        with engine.begin() as conexion:
            conexion.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": ids})
            if apartados:
                conexion.execute(
                    text("UPDATE users SET is_active = true WHERE id = ANY(:ids)"),
                    {"ids": apartados},
                )


@pytest.fixture
def dos_admins(engine_de_test):
    """Dos admins con commit, los únicos activos de la base mientras dura el test."""
    with solo_estos_usuarios(engine_de_test, ["ADMIN", "ADMIN"]) as ids:
        yield ids


@pytest.fixture
def tres_admins_y_un_asistente(engine_de_test):
    """Tres admins (los únicos activos) y un asistente, con commit."""
    with solo_estos_usuarios(engine_de_test, ["ADMIN", "ADMIN", "ADMIN", "ATTENDEE"]) as ids:
        yield ids


def cambiar_a_la_vez(
    engine,
    url_db: str,
    pedidos: list[tuple[UUID, UUID, dict]],
    bloqueados: list[UUID],
    *,
    en_orden: bool = False,
) -> list:
    """Cada `(actor, objetivo, cuerpo)` en su hilo, todos frenados en el bloqueo de `bloqueados`
    hasta que se suelta. Con `en_orden`, cada pedido arranca recién cuando el anterior ya espera
    el bloqueo, y Postgres se lo entrega en ese orden. Devuelve las respuestas en el orden de los
    pedidos; falla si algún hilo quedó trabado."""
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
    respuestas: list = [None] * len(pedidos)
    barrera = threading.Barrier(1 if en_orden else len(pedidos))

    def correr(indice: int, actor: UUID, objetivo: UUID, cuerpo: dict) -> None:
        cliente = TestClient(app)
        token = crear_access_token(actor, SECRETO, 5)
        barrera.wait()
        respuestas[indice] = cliente.patch(
            f"/admin/users/{objetivo}",
            json=cuerpo,
            headers={"Authorization": f"Bearer {token}"},
        )

    try:
        with engine.connect() as cerrojo:
            transaccion = cerrojo.begin()
            cerrojo.execute(
                text("SELECT id FROM users WHERE id = ANY(:ids) ORDER BY id FOR UPDATE"),
                {"ids": sorted(bloqueados)},
            )
            hilos = [threading.Thread(target=correr, args=(i, *p)) for i, p in enumerate(pedidos)]
            try:
                for frenados, hilo in enumerate(hilos, start=1):
                    hilo.start()
                    if en_orden:
                        esperar_frenados_en_usuarios(engine, frenados)
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

    a_asistente = {"role": "ATTENDEE"}

    respuestas = cambiar_a_la_vez(
        engine_de_test,
        url_db,
        [(uno, otro, a_asistente), (otro, uno, a_asistente)],
        bloqueados=dos_admins,
    )

    assert sorted(r.status_code for r in respuestas) == [200, 409], [r.text for r in respuestas]
    [rechazada] = [r for r in respuestas if r.status_code == 409]
    assert rechazada.json()["type"] == "last-admin"
    assert rechazada.json()["title"] == "Tiene que quedar al menos un administrador activo"
    assert len(admins_activos(engine_de_test, dos_admins)) == 1
    assert len(admins_activos(engine_de_test)) == 1


def test_el_admin_degradado_mientras_esperaba_no_puede_dar_admin_a_otro(
    engine_de_test, url_db, tres_admins_y_un_asistente
):
    """A degrada a B y, a la vez, B le da ADMIN a X. A llega primero al bloqueo: cuando B lo
    obtiene ya no es admin, así que recibe 403 y X sigue siendo asistente."""
    a, b, c, x = tres_admins_y_un_asistente

    degrada, promueve = cambiar_a_la_vez(
        engine_de_test,
        url_db,
        [(a, b, {"role": "ATTENDEE"}), (b, x, {"role": "ADMIN"})],
        bloqueados=tres_admins_y_un_asistente,
        en_orden=True,
    )

    assert degrada.status_code == 200, degrada.text
    assert promueve.status_code == 403, promueve.text
    assert promueve.json()["type"] == "forbidden"
    assert sorted(admins_activos(engine_de_test, tres_admins_y_un_asistente)) == sorted([a, c])


@pytest.fixture
def dos_admins_y_dos_asistentes(engine_de_test):
    """Dos admins (los únicos activos) y dos asistentes, con commit."""
    with solo_estos_usuarios(engine_de_test, ["ADMIN", "ADMIN", "ATTENDEE", "ATTENDEE"]) as ids:
        yield ids


def test_dos_admins_que_ponen_el_mismo_email_a_dos_usuarios_a_la_vez_un_200_y_un_409(
    engine_de_test, url_db, dos_admins_y_dos_asistentes
):
    """La unicidad la garantiza el índice único de la base: el segundo que guarda choca con el
    email que el primero ya confirmó, y eso es un 409 email-taken, nunca un 500."""
    uno, otro, x, y = dos_admins_y_dos_asistentes
    with engine_de_test.connect() as conexion:
        antes = dict(
            conexion.execute(
                text("SELECT id, email FROM users WHERE id = ANY(:ids)"), {"ids": [x, y]}
            ).all()
        )
    destino = f"ca{uuid4().hex[:8]}destino@mail.com"

    respuestas = cambiar_a_la_vez(
        engine_de_test,
        url_db,
        [(uno, x, {"email": destino}), (otro, y, {"email": destino.upper()})],
        bloqueados=[uno, otro],
    )

    assert sorted(r.status_code for r in respuestas) == [200, 409], [r.text for r in respuestas]
    [rechazada] = [r for r in respuestas if r.status_code == 409]
    assert rechazada.json()["type"] == "email-taken"
    with engine_de_test.connect() as conexion:
        despues = dict(
            conexion.execute(
                text("SELECT id, email FROM users WHERE id = ANY(:ids)"), {"ids": [x, y]}
            ).all()
        )
    [ganador] = [i for i, e in despues.items() if e == destino]
    [perdedor] = [i for i in (x, y) if i != ganador]
    assert despues[perdedor] == antes[perdedor]
