"""Las reglas de las inscripciones valen en la base, aunque el código no las revise."""

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
        {"e": f"ie{uuid4().hex[:8]}@mail.com", "h": hashear(secrets.token_urlsafe(16)), "r": rol},
    ).scalar_one()


def insertar_evento(conexion: Connection, organizador: UUID) -> UUID:
    return conexion.execute(
        text(
            "INSERT INTO events (name, start_at, end_at, capacity, status, organizer_id)"
            " VALUES ('PyCon', '2030-01-10T13:00:00Z', '2030-01-10T23:00:00Z', 10, 'PUBLISHED',"
            " :o) RETURNING id"
        ),
        {"o": organizador},
    ).scalar_one()


def inscribir(conexion: Connection, usuario: UUID, evento: UUID, estado: str = "ACTIVE") -> UUID:
    return conexion.execute(
        text(
            "INSERT INTO registrations (user_id, event_id, status) VALUES (:u, :e, :s) RETURNING id"
        ),
        {"u": usuario, "e": evento, "s": estado},
    ).scalar_one()


def contar(conexion: Connection, consulta: str, **parametros) -> int:
    return conexion.execute(text(consulta), parametros).scalar_one()


@pytest.fixture
def inscripto(conexion) -> tuple[UUID, UUID]:
    """(usuario, evento), sin inscripciones todavía."""
    return insertar_usuario(conexion), insertar_evento(conexion, insertar_usuario(conexion))


def test_una_inscripcion_nueva_queda_activa_y_sin_fecha_de_cancelacion(conexion, inscripto):
    usuario, evento = inscripto

    id_ = conexion.execute(
        text("INSERT INTO registrations (user_id, event_id) VALUES (:u, :e) RETURNING id"),
        {"u": usuario, "e": evento},
    ).scalar_one()

    fila = conexion.execute(
        text("SELECT status, cancelled_at, created_at FROM registrations WHERE id = :id"),
        {"id": id_},
    ).one()
    assert (fila.status, fila.cancelled_at) == ("ACTIVE", None)
    assert fila.created_at is not None


def test_una_segunda_inscripcion_activa_de_la_misma_persona_falla_por_el_indice(
    conexion, inscripto
):
    usuario, evento = inscripto
    inscribir(conexion, usuario, evento)

    with pytest.raises(IntegrityError, match="uq_registrations_activa"):
        inscribir(conexion, usuario, evento)


def test_puede_haber_varias_canceladas_y_una_activa_de_la_misma_persona(conexion, inscripto):
    usuario, evento = inscripto

    inscribir(conexion, usuario, evento, "CANCELLED")
    inscribir(conexion, usuario, evento, "CANCELLED")
    inscribir(conexion, usuario, evento)

    total = contar(conexion, "SELECT count(*) FROM registrations WHERE user_id = :u", u=usuario)
    assert total == 3


def test_el_estado_solo_acepta_activa_o_cancelada(conexion, inscripto):
    usuario, evento = inscripto

    with pytest.raises(DataError, match="registration_status"):
        inscribir(conexion, usuario, evento, "PENDING")


def test_no_se_inscribe_a_un_evento_ni_un_usuario_que_no_existen(conexion, inscripto):
    usuario, evento = inscripto

    with pytest.raises(IntegrityError, match="fk_registrations_event"), conexion.begin_nested():
        inscribir(conexion, usuario, uuid4())
    with pytest.raises(IntegrityError, match="fk_registrations_user"):
        inscribir(conexion, uuid4(), evento)


def test_borrar_el_evento_borra_sus_inscripciones(conexion, inscripto):
    usuario, evento = inscripto
    inscribir(conexion, usuario, evento, "CANCELLED")

    conexion.execute(text("DELETE FROM events WHERE id = :e"), {"e": evento})

    assert contar(conexion, "SELECT count(*) FROM registrations WHERE event_id = :e", e=evento) == 0


def test_las_busquedas_por_evento_y_por_usuario_tienen_indice(conexion):
    indices = set(
        conexion.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
                " AND tablename = 'registrations'"
            )
        ).scalars()
    )

    assert {
        "uq_registrations_activa",
        "ix_registrations_event_id",
        "ix_registrations_user_id",
    } <= indices


def test_el_downgrade_a_0004_borra_la_tabla_y_su_tipo(conexion):
    def existe() -> tuple[bool, bool]:
        tabla = conexion.execute(text("SELECT to_regclass('registrations') IS NOT NULL"))
        tipo = conexion.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'registration_status')")
        )
        return tabla.scalar_one(), tipo.scalar_one()

    revertir(conexion, "0004")
    assert existe() == (False, False)

    migrar(conexion, "head")
    assert existe() == (True, True)
