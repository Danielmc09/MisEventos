"""Base de datos de los tests de integración: cuál es, crearla y migrarla."""

from collections.abc import Mapping
from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import Connection
from sqlalchemy.engine import URL, make_url

BACKEND = Path(__file__).resolve().parents[2]
BASE_POR_DEFECTO = "miseventos_test"


def url_de_test(entorno: Mapping[str, str]) -> URL:
    """TEST_DATABASE_URL, o DATABASE_URL con la base cambiada a miseventos_test."""
    if entorno.get("TEST_DATABASE_URL"):
        url = make_url(entorno["TEST_DATABASE_URL"])
    elif entorno.get("DATABASE_URL"):
        url = make_url(entorno["DATABASE_URL"]).set(database=BASE_POR_DEFECTO)
    else:
        raise RuntimeError("Los tests de integración necesitan TEST_DATABASE_URL o DATABASE_URL")
    # Los tests crean, migran y revierten: nunca contra una base que no sea de test.
    if not (url.database or "").endswith("_test"):
        raise RuntimeError(f"La base de test tiene que terminar en _test: {url.database!r}")
    return url


def asegurar_base(url: URL) -> None:
    """Crea la base de test si no existe, conectándose a la base `postgres` del servidor."""
    servidor = url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(servidor.render_as_string(hide_password=False), autocommit=True) as c:
        existe = c.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
        ).fetchone()
        if not existe:
            # CREATE DATABASE no acepta parámetros: el nombre va como identificador citado.
            c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))


def _alembic(conexion: Connection) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["connection"] = conexion
    return config


def migrar(conexion: Connection, revision: str = "head") -> None:
    command.upgrade(_alembic(conexion), revision)


def revertir(conexion: Connection, revision: str = "base") -> None:
    command.downgrade(_alembic(conexion), revision)
