from alembic import context
from sqlalchemy import Connection, create_engine, pool
from sqlmodel import SQLModel

import app.models  # noqa: F401 - aplica la convención de nombres y registra los modelos
from app.core.config import Settings

config = context.config
target_metadata = SQLModel.metadata


def _url() -> str:
    return config.attributes.get("database_url") or Settings().database_url


def _migrar(conexion: Connection) -> None:
    context.configure(connection=conexion, target_metadata=target_metadata, compare_type=True)
    # Si la conexión ya trae una transacción (los tests), Alembic no abre ni commitea la suya.
    with context.begin_transaction():
        context.run_migrations()


def migrar_offline() -> None:
    """`alembic upgrade head --sql`: genera el SQL sin conectarse, para revisarlo."""
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def migrar_online() -> None:
    conexion = config.attributes.get("connection")
    if conexion is not None:
        _migrar(conexion)
        return
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as conexion:
        _migrar(conexion)


if context.is_offline_mode():
    migrar_offline()
else:
    migrar_online()
