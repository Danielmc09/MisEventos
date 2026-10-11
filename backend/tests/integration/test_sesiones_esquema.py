"""Las reglas de sesiones, ponentes y vínculos valen en la base, aunque el código no valide."""

from uuid import UUID, uuid4

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
            " VALUES (:email, '$argon2id$x', 'ORGANIZER') RETURNING id"
        ),
        {"email": f"se{uuid4().hex[:8]}@mail.com"},
    ).scalar_one()


def insertar_evento(conexion: Connection, organizador: UUID) -> UUID:
    return conexion.execute(
        text(
            "INSERT INTO events (name, start_at, end_at, capacity, status, organizer_id)"
            " VALUES ('PyCon', '2030-01-10T08:00:00Z', '2030-01-10T20:00:00Z', 100, 'DRAFT', :orga)"
            " RETURNING id"
        ),
        {"orga": organizador},
    ).scalar_one()


def insertar_sesion(conexion: Connection, evento: UUID, **cambios) -> UUID:
    datos = {"titulo": "Testing en Python", "inicio": INICIO, "fin": FIN, "capacidad": None}
    return conexion.execute(
        text(
            "INSERT INTO sessions (event_id, title, start_at, end_at, capacity)"
            " VALUES (:evento, :titulo, :inicio, :fin, :capacidad) RETURNING id"
        ),
        datos | cambios | {"evento": evento},
    ).scalar_one()


def insertar_ponente(conexion: Connection, organizador: UUID, nombre: str = "Ana Pérez") -> UUID:
    return conexion.execute(
        text("INSERT INTO speakers (full_name, created_by) VALUES (:nombre, :orga) RETURNING id"),
        {"nombre": nombre, "orga": organizador},
    ).scalar_one()


def vincular(conexion: Connection, sesion: UUID, ponente: UUID) -> None:
    conexion.execute(
        text("INSERT INTO session_speakers (session_id, speaker_id) VALUES (:sesion, :ponente)"),
        {"sesion": sesion, "ponente": ponente},
    )


def contar(conexion: Connection, consulta: str, **parametros) -> int:
    return conexion.execute(text(consulta), parametros).scalar_one()


@pytest.fixture
def evento(conexion) -> tuple[UUID, UUID]:
    """(organizador, evento)"""
    organizador = insertar_organizador(conexion)
    return organizador, insertar_evento(conexion, organizador)


def test_la_base_acepta_una_sesion_en_los_limites(conexion, evento):
    _, id_evento = evento

    insertar_sesion(conexion, id_evento, titulo="abc", capacidad=1)
    insertar_sesion(conexion, id_evento, titulo="a" * 150, capacidad=None)

    assert contar(conexion, "SELECT count(*) FROM sessions WHERE event_id = :e", e=id_evento) == 2


@pytest.mark.parametrize(
    ("cambios", "constraint"),
    [
        ({"fin": INICIO}, "ck_sessions_fechas_ordenadas"),
        ({"fin": "2030-01-10T14:59:59Z"}, "ck_sessions_fechas_ordenadas"),
        ({"titulo": "ab"}, "ck_sessions_largo_titulo"),
        ({"capacidad": 0}, "ck_sessions_capacidad"),
    ],
    ids=["fin-igual-inicio", "fin-antes-inicio", "titulo-2", "capacidad-0"],
)
def test_la_base_rechaza_una_sesion_que_rompe_una_regla(conexion, evento, cambios, constraint):
    _, id_evento = evento

    with pytest.raises(IntegrityError, match=constraint):
        insertar_sesion(conexion, id_evento, **cambios)


def test_la_base_rechaza_un_ponente_con_nombre_de_un_caracter(conexion, evento):
    organizador, _ = evento
    insertar_ponente(conexion, organizador, "Al")

    with pytest.raises(IntegrityError, match="ck_speakers_largo_nombre"):
        insertar_ponente(conexion, organizador, "A")


def test_borrar_un_evento_borra_sus_sesiones_y_sus_vinculos(conexion, evento):
    organizador, id_evento = evento
    ponente = insertar_ponente(conexion, organizador)
    sesion = insertar_sesion(conexion, id_evento)
    vincular(conexion, sesion, ponente)

    conexion.execute(text("DELETE FROM events WHERE id = :e"), {"e": id_evento})

    assert contar(conexion, "SELECT count(*) FROM sessions WHERE event_id = :e", e=id_evento) == 0
    assert (
        contar(conexion, "SELECT count(*) FROM session_speakers WHERE session_id = :s", s=sesion)
        == 0
    )
    # El ponente es global: sobrevive al evento.
    assert contar(conexion, "SELECT count(*) FROM speakers WHERE id = :p", p=ponente) == 1


def test_un_ponente_con_sesiones_no_se_puede_borrar(conexion, evento):
    organizador, id_evento = evento
    ponente = insertar_ponente(conexion, organizador)
    vincular(conexion, insertar_sesion(conexion, id_evento), ponente)

    with pytest.raises(IntegrityError, match="fk_session_speakers_speaker_id_speakers"):
        conexion.execute(text("DELETE FROM speakers WHERE id = :p"), {"p": ponente})


def test_un_ponente_no_se_repite_en_la_misma_sesion(conexion, evento):
    organizador, id_evento = evento
    ponente = insertar_ponente(conexion, organizador)
    sesion = insertar_sesion(conexion, id_evento)
    vincular(conexion, sesion, ponente)

    with pytest.raises(IntegrityError, match="pk_session_speakers"):
        vincular(conexion, sesion, ponente)


def test_las_busquedas_por_evento_y_por_ponente_tienen_indice(conexion):
    indices = set(
        conexion.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
                " AND tablename IN ('sessions', 'session_speakers')"
            )
        ).scalars()
    )

    assert {"ix_sessions_event_id", "ix_session_speakers_speaker_id"} <= indices


def test_el_downgrade_a_0003_borra_las_tres_tablas(conexion):
    tablas = ("sessions", "speakers", "session_speakers")

    def existen() -> list[bool]:
        return [
            conexion.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": t}).scalar_one()
            for t in tablas
        ]

    revertir(conexion, "0003")
    assert existen() == [False, False, False]

    migrar(conexion, "head")
    assert existen() == [True, True, True]
