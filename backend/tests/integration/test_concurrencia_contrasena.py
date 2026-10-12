"""El admin restablece la contraseña de un usuario mientras ese usuario la está cambiando. El
resultado tiene que ser uno de los dos órdenes posibles, nunca una mezcla: si el reset confirmó
primero, el cambio ve la temporal nueva, su contraseña actual ya no sirve (422) y la temporal
queda vigente.

Corre fuera de la transacción del fixture (cada request hace commit de verdad), con datos propios
que se borran al final. Para que sea determinista, el test toma primero el bloqueo de la fila del
usuario, deja que el reset quede esperándolo, después el cambio, y recién ahí lo suelta: Postgres
se lo entrega en ese orden. Si el cambio leyera al usuario sin bloquearlo, verificaría la
contraseña vieja antes de esperar y, al soltarse, pisaría la temporal del reset."""

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
from app.core.contrasenas import hashear, verificar
from app.core.tokens import crear_access_token
from app.main import create_app

pytestmark = pytest.mark.integration

SECRETO = "concurrencia-" + "x" * 32
ESPERA_MAXIMA = 30  # segundos que un hilo puede tardar antes de darlo por trabado


def esperar_frenados(engine, cuantos: int, segundos: float = 15) -> None:
    """Hasta que `cuantos` conexiones esperan un bloqueo sobre la tabla users, ya sea al leerla
    para escribir o al actualizarla."""
    limite = time.monotonic() + segundos
    consulta = text(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
        " AND wait_event_type = 'Lock' AND query ILIKE '%users%'"
    )
    while time.monotonic() < limite:
        with engine.connect() as conexion:
            if conexion.execute(consulta).scalar_one() >= cuantos:
                return
        time.sleep(0.05)
    pytest.fail(f"Los {cuantos} requests nunca esperaron el bloqueo del usuario")


@pytest.fixture
def admin_y_usuario(engine_de_test):
    """Un admin y un usuario con commit, y la contraseña de ese usuario."""
    prefijo = "cc" + uuid4().hex[:8]
    clave = secrets.token_urlsafe(16)
    insertar = text(
        "INSERT INTO users (email, password_hash, role)"
        " VALUES (:e, :h, CAST(:r AS user_role)) RETURNING id"
    )
    with engine_de_test.begin() as conexion:
        admin = conexion.execute(
            insertar,
            {
                "e": f"{prefijo}admin@mail.com",
                "h": hashear(secrets.token_urlsafe(16)),
                "r": "ADMIN",
            },
        ).scalar_one()
        usuario = conexion.execute(
            insertar, {"e": f"{prefijo}ana@mail.com", "h": hashear(clave), "r": "ATTENDEE"}
        ).scalar_one()
    try:
        yield admin, usuario, clave
    finally:
        with engine_de_test.begin() as conexion:
            conexion.execute(
                text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": [admin, usuario]}
            )


def test_un_cambio_de_contrasena_no_pisa_un_reset_que_confirmo_antes(
    engine_de_test, url_db, admin_y_usuario
):
    admin, usuario, clave = admin_y_usuario
    nueva = secrets.token_urlsafe(16)
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
    respuestas: dict[str, object] = {}

    def con_token(actor: UUID) -> dict:
        return {"Authorization": f"Bearer {crear_access_token(actor, SECRETO, 5)}"}

    def restablecer() -> None:
        respuestas["reset"] = TestClient(app).post(
            f"/admin/users/{usuario}/reset-password", headers=con_token(admin)
        )

    def cambiar() -> None:
        respuestas["cambio"] = TestClient(app).patch(
            "/auth/me/password",
            json={"current_password": clave, "new_password": nueva},
            headers=con_token(usuario),
        )

    hilos = [threading.Thread(target=restablecer), threading.Thread(target=cambiar)]
    try:
        with engine_de_test.connect() as cerrojo:
            transaccion = cerrojo.begin()
            cerrojo.execute(text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": usuario})
            try:
                # El reset llega primero a la cola del bloqueo; el cambio, detrás.
                for frenados, hilo in enumerate(hilos, start=1):
                    hilo.start()
                    esperar_frenados(engine_de_test, frenados)
            finally:
                transaccion.commit()
            for hilo in hilos:
                hilo.join(timeout=ESPERA_MAXIMA)
            assert not any(h.is_alive() for h in hilos), "un request quedó trabado"
    finally:
        engine_app.dispose()

    reset, cambio = respuestas["reset"], respuestas["cambio"]
    assert reset.status_code == 200, reset.text
    temporal = reset.json()["temporary_password"]
    with engine_de_test.connect() as conexion:
        password_hash, must_change_password = conexion.execute(
            text("SELECT password_hash, must_change_password FROM users WHERE id = :id"),
            {"id": usuario},
        ).one()
    # El reset confirmó primero: la temporal es la vigente y el cambio con la vieja no entra.
    assert verificar(password_hash, temporal), "el cambio pisó la temporal del reset"
    assert not verificar(password_hash, nueva)
    assert must_change_password is True
    assert cambio.status_code == 422, cambio.text
    assert [e["field"] for e in cambio.json()["errors"]] == ["current_password"]
