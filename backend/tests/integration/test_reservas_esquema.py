"""Las reglas de las reservas de sesiones valen en la base, aunque el código no las revise."""

import secrets
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DataError, IntegrityError

from app.core.contrasenas import hashear
from tests.integration.infraestructura import migrar, revertir

pytestmark = pytest.mark.integration


def insertar_usuario(conexion: Connection, rol: str = "ATTENDEE") -> UUID:
    return conexion.execute(
        text("INSERT INTO users (email, password_hash, role) VALUES (:e, :h, :r) RETURNING id"),
        {"e": f"re{uuid4().hex[:8]}@mail.com", "h": hashear(secrets.token_urlsafe(16)), "r": rol},
    ).scalar_one()


def insertar_sesion(conexion: Connection) -> UUID:
    organizador = insertar_usuario(conexion, "ORGANIZER")
    evento = conexion.execute(
        text(
            "INSERT INTO events (name, start_at, end_at, capacity, status, organizer_id)"
            " VALUES ('PyCon', '2030-01-10T13:00:00Z', '2030-01-10T23:00:00Z', 10, 'PUBLISHED',"
            " :o) RETURNING id"
        ),
        {"o": organizador},
    ).scalar_one()
    return conexion.execute(
        text(
            "INSERT INTO sessions (event_id, title, start_at, end_at)"
            " VALUES (:e, 'Testing en Python', '2030-01-10T15:00:00Z', '2030-01-10T16:00:00Z')"
            " RETURNING id"
        ),
        {"e": evento},
    ).scalar_one()


def reservar(conexion: Connection, usuario: UUID, sesion: UUID, estado: str = "ACTIVE") -> UUID:
    return conexion.execute(
        text(
            "INSERT INTO session_registrations (user_id, session_id, status)"
            " VALUES (:u, :s, :e) RETURNING id"
        ),
        {"u": usuario, "s": sesion, "e": estado},
    ).scalar_one()


def contar(conexion: Connection, consulta: str, **parametros) -> int:
    return conexion.execute(text(consulta), parametros).scalar_one()


@pytest.fixture
def reservable(conexion) -> tuple[UUID, UUID]:
    """(usuario, sesión), sin reservas todavía."""
    return insertar_usuario(conexion), insertar_sesion(conexion)


def test_una_reserva_nueva_queda_activa_y_sin_fecha_de_cancelacion(conexion, reservable):
    usuario, sesion = reservable

    id_ = conexion.execute(
        text(
            "INSERT INTO session_registrations (user_id, session_id) VALUES (:u, :s) RETURNING id"
        ),
        {"u": usuario, "s": sesion},
    ).scalar_one()

    fila = conexion.execute(
        text(
            "SELECT status, cancelled_at, created_at, updated_at FROM session_registrations"
            " WHERE id = :id"
        ),
        {"id": id_},
    ).one()
    assert (fila.status, fila.cancelled_at) == ("ACTIVE", None)
    assert fila.created_at is not None
    assert fila.updated_at is not None


def test_una_segunda_reserva_activa_de_la_misma_persona_falla_por_el_indice(conexion, reservable):
    usuario, sesion = reservable
    reservar(conexion, usuario, sesion)

    with pytest.raises(IntegrityError, match="uq_session_registrations_activa"):
        reservar(conexion, usuario, sesion)


def test_puede_haber_varias_canceladas_y_una_activa_de_la_misma_persona(conexion, reservable):
    usuario, sesion = reservable

    reservar(conexion, usuario, sesion, "CANCELLED")
    reservar(conexion, usuario, sesion, "CANCELLED")
    reservar(conexion, usuario, sesion)

    consulta = "SELECT count(*) FROM session_registrations WHERE user_id = :u"
    assert contar(conexion, consulta, u=usuario) == 3


def test_el_estado_solo_acepta_activa_o_cancelada(conexion, reservable):
    usuario, sesion = reservable

    with pytest.raises(DataError, match="session_registration_status"):
        reservar(conexion, usuario, sesion, "PENDING")


def test_no_se_reserva_una_sesion_ni_para_un_usuario_que_no_existen(conexion, reservable):
    usuario, sesion = reservable

    with (
        pytest.raises(IntegrityError, match="fk_session_registrations_session_id"),
        conexion.begin_nested(),
    ):
        reservar(conexion, usuario, uuid4())
    with pytest.raises(IntegrityError, match="fk_session_registrations_user_id"):
        reservar(conexion, uuid4(), sesion)


def test_borrar_la_sesion_borra_sus_reservas(conexion, reservable):
    usuario, sesion = reservable
    reservar(conexion, usuario, sesion, "CANCELLED")

    conexion.execute(text("DELETE FROM sessions WHERE id = :s"), {"s": sesion})

    consulta = "SELECT count(*) FROM session_registrations WHERE session_id = :s"
    assert contar(conexion, consulta, s=sesion) == 0


def test_el_trigger_mantiene_updated_at_al_cancelar(conexion, reservable):
    usuario, sesion = reservable
    id_ = reservar(conexion, usuario, sesion)
    conexion.execute(
        text("UPDATE session_registrations SET updated_at = '2020-01-01T00:00:00Z' WHERE id = :id"),
        {"id": id_},
    )

    conexion.execute(
        text(
            "UPDATE session_registrations SET status = 'CANCELLED', cancelled_at = now()"
            " WHERE id = :id"
        ),
        {"id": id_},
    )

    actualizada = conexion.execute(
        text(
            "SELECT updated_at > '2020-01-02T00:00:00Z' FROM session_registrations WHERE id = :id"
        ),
        {"id": id_},
    ).scalar_one()
    assert actualizada is True


def test_las_busquedas_por_sesion_y_por_usuario_tienen_indice(conexion):
    indices = set(
        conexion.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
                " AND tablename = 'session_registrations'"
            )
        ).scalars()
    )

    assert {
        "uq_session_registrations_activa",
        "ix_session_registrations_session_id",
        "ix_session_registrations_user_id",
    } <= indices


def test_el_downgrade_a_0005_borra_la_tabla_y_su_tipo(conexion):
    def existe() -> tuple[bool, bool]:
        tabla = conexion.execute(text("SELECT to_regclass('session_registrations') IS NOT NULL"))
        tipo = conexion.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_type"
                " WHERE typname = 'session_registration_status')"
            )
        )
        return tabla.scalar_one(), tipo.scalar_one()

    revertir(conexion, "0005")
    assert existe() == (False, False)

    migrar(conexion, "head")
    assert existe() == (True, True)
