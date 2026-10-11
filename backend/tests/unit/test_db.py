from typing import Annotated

import pytest
from fastapi import Depends
from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, MetaData, String, Table
from sqlalchemy.exc import OperationalError
from sqlalchemy.schema import CreateTable
from sqlmodel import Session, SQLModel

from app.core.db import get_session, sesion_transaccional
from app.core.excepciones import Conflict


class SesionDoble:
    """Registra qué se hizo con la transacción. `falla_commit` simula una base que rechaza."""

    def __init__(self, falla_commit: bool = False) -> None:
        self.falla_commit = falla_commit
        self.llamadas: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.llamadas.append("close")

    def commit(self):
        self.llamadas.append("commit")
        if self.falla_commit:
            raise OperationalError("COMMIT", {}, Exception("conexión perdida"))

    def rollback(self):
        self.llamadas.append("rollback")


def test_la_sesion_hace_commit_al_terminar_bien():
    doble = SesionDoble()
    generador = sesion_transaccional(lambda: doble)

    assert next(generador) is doble
    with pytest.raises(StopIteration):
        next(generador)

    assert doble.llamadas == ["commit", "close"]


def test_la_sesion_hace_rollback_si_hay_un_error_y_lo_propaga():
    doble = SesionDoble()
    generador = sesion_transaccional(lambda: doble)
    next(generador)

    with pytest.raises(ValueError, match="fallo del servicio"):
        generador.throw(ValueError("fallo del servicio"))

    assert doble.llamadas == ["rollback", "close"]


@pytest.fixture
def rutas_con_sesion(app):
    @app.get("/escribe")
    def escribe(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
        return {"ok": "si"}

    @app.get("/choca")
    def choca(session: Annotated[Session, Depends(get_session)]) -> None:
        raise Conflict("ya existe")

    return app


def test_un_error_de_dominio_revierte_la_transaccion_del_request(rutas_con_sesion, cliente):
    doble = SesionDoble()
    rutas_con_sesion.state.sesiones = lambda: doble

    respuesta = cliente.get("/choca")

    assert respuesta.status_code == 409
    assert doble.llamadas == ["rollback", "close"]


def test_si_el_commit_falla_el_cliente_no_recibe_un_200(rutas_con_sesion, cliente):
    doble = SesionDoble(falla_commit=True)
    rutas_con_sesion.state.sesiones = lambda: doble

    respuesta = cliente.get("/escribe")

    assert respuesta.status_code == 500
    assert respuesta.json()["type"] == "internal-error"


def test_la_metadata_nombra_constraints_e_indices_con_la_convencion():
    import app.models  # noqa: F401 - aplica la convención a SQLModel.metadata

    metadata = MetaData(naming_convention=SQLModel.metadata.naming_convention)
    Table("events", metadata, Column("id", Integer, primary_key=True))
    tabla = Table(
        "registrations",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("event_id", ForeignKey("events.id")),
        Column("email", String, unique=True, index=True),
        Column("cupo", Integer),
        CheckConstraint("cupo > 0", name="cupo_positivo"),
    )

    ddl = str(CreateTable(tabla).compile())
    nombres = {c.name for c in tabla.constraints} | {i.name for i in tabla.indexes}

    assert nombres == {
        "pk_registrations",
        "fk_registrations_event_id_events",
        "uq_registrations_email",
        "ck_registrations_cupo_positivo",
        "ix_registrations_email",
    }
    assert "CONSTRAINT pk_registrations" in ddl
