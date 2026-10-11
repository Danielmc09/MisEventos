"""Fixtures de integración: PostgreSQL real, migrado una vez por sesión, y una transacción
que se revierte al terminar cada test."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine
from sqlmodel import Session

from app.core.config import Settings
from app.main import create_app
from tests.integration.infraestructura import asegurar_base, migrar, url_de_test


@pytest.fixture(scope="session")
def url_db() -> str:
    url = url_de_test(os.environ)
    asegurar_base(url)
    return url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def engine_de_test(url_db) -> Iterator[Engine]:
    engine = create_engine(url_db)
    with engine.begin() as conexion:
        migrar(conexion)
    yield engine
    engine.dispose()


@pytest.fixture
def conexion(engine_de_test) -> Iterator[Connection]:
    """Todo lo que el test hace, incluido el DDL, se revierte al final."""
    with engine_de_test.connect() as conexion:
        transaccion = conexion.begin()
        yield conexion
        transaccion.rollback()


@pytest.fixture
def cliente_db(conexion, url_db) -> Iterator[TestClient]:
    """La app real sobre la conexión del test. El commit de cada request queda en un savepoint,
    así que el rollback del test también lo deshace."""
    settings = Settings(
        _env_file=None,
        DATABASE_URL=url_db,
        JWT_SECRET="integracion-" + "x" * 32,
        ACCESS_TOKEN_MINUTES=60,
        CORS_ORIGINS="http://localhost:5173",
    )
    app = create_app(settings)
    app.state.sesiones = lambda: Session(bind=conexion, join_transaction_mode="create_savepoint")
    with TestClient(app) as cliente:
        yield cliente
