"""Las reglas de un evento valen en la base, aunque el código no las valide."""

from uuid import UUID

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from tests.integration.infraestructura import migrar, revertir

pytestmark = pytest.mark.integration

INICIO = "2030-01-10T15:00:00Z"
FIN = "2030-01-10T18:00:00Z"


def insertar_organizador(conexion: Connection) -> UUID:
    return conexion.execute(
        text(
            "INSERT INTO users (email, password_hash, role)"
            " VALUES ('orga@mail.com', '$argon2id$x', 'ORGANIZER') RETURNING id"
        )
    ).scalar_one()


def insertar_evento(conexion: Connection, organizador: UUID, **cambios) -> None:
    # SQL directo, sin pasar por el modelo ni por el schema.
    datos = {"nombre": "PyCon", "inicio": INICIO, "fin": FIN, "capacidad": 10} | cambios
    conexion.execute(
        text(
            "INSERT INTO events (name, start_at, end_at, capacity, status, organizer_id)"
            " VALUES (:nombre, :inicio, :fin, :capacidad, 'DRAFT', :organizador)"
        ),
        datos | {"organizador": organizador},
    )


def test_la_base_acepta_un_evento_en_los_limites(conexion):
    organizador = insertar_organizador(conexion)

    insertar_evento(conexion, organizador, nombre="abc", capacidad=1)
    insertar_evento(conexion, organizador, nombre="a" * 150, capacidad=100_000)

    assert conexion.execute(text("SELECT count(*) FROM events")).scalar_one() == 2


@pytest.mark.parametrize(
    ("cambios", "constraint"),
    [
        ({"fin": INICIO}, "ck_events_fechas_ordenadas"),
        ({"fin": "2030-01-10T14:59:59Z"}, "ck_events_fechas_ordenadas"),
        ({"capacidad": 0}, "ck_events_capacidad"),
        ({"capacidad": 100_001}, "ck_events_capacidad"),
        ({"nombre": "ab"}, "ck_events_largo_nombre"),
    ],
    ids=["fin-igual-inicio", "fin-antes-inicio", "capacidad-0", "capacidad-100001", "nombre-2"],
)
def test_la_base_rechaza_un_evento_que_rompe_una_regla(conexion, cambios, constraint):
    organizador = insertar_organizador(conexion)

    with pytest.raises(IntegrityError, match=constraint):
        insertar_evento(conexion, organizador, **cambios)


def test_el_downgrade_a_0002_borra_events_y_su_tipo(conexion):
    revertir(conexion, "0002")
    assert conexion.execute(text("SELECT to_regclass('public.events') IS NULL")).scalar_one()
    assert conexion.execute(text("SELECT to_regtype('event_status') IS NULL")).scalar_one()

    migrar(conexion, "head")
    assert conexion.execute(text("SELECT to_regclass('public.events') IS NOT NULL")).scalar_one()
