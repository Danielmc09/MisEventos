from collections.abc import Callable, Iterator
from functools import partial
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session, create_engine

FabricaDeSesiones = Callable[[], Session]


def crear_fabrica_de_sesiones(database_url: str) -> FabricaDeSesiones:
    return partial(Session, create_engine(database_url, pool_pre_ping=True))


def sesion_transaccional(fabrica: FabricaDeSesiones) -> Iterator[Session]:
    """Una transacción por request: commit si terminó bien, rollback si algo falló."""
    with fabrica() as session:
        try:
            yield session
        except BaseException:
            session.rollback()
            raise
        session.commit()


def get_session(request: Request) -> Iterator[Session]:
    yield from sesion_transaccional(request.app.state.sesiones)


# scope="function": el commit corre ANTES de enviar la respuesta. Con el scope por defecto
# corre después, y un commit que falla le llegaría al cliente como un 200.
SesionDB = Annotated[Session, Depends(get_session, scope="function")]
