from collections.abc import Callable, Iterator
from functools import partial

from fastapi import Request
from sqlmodel import Session, create_engine

FabricaDeSesiones = Callable[[], Session]


def crear_fabrica_de_sesiones(database_url: str) -> FabricaDeSesiones:
    return partial(Session, create_engine(database_url, pool_pre_ping=True))


def sesion_transaccional(fabrica: FabricaDeSesiones) -> Iterator[Session]:
    with fabrica() as session:
        yield session


def get_session(request: Request) -> Iterator[Session]:
    yield from sesion_transaccional(request.app.state.sesiones)
