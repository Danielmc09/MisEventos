"""El choque de ponentes lo resuelve la base: devuelve, por cada ponente, solo la primera sesión
que se cruza con el horario pedido, fuera de eventos cancelados y sin contar la propia sesión."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session

from app.repositories.sesiones import RepositorioSesiones
from tests.integration.test_eventos import auth, usuario_con_rol
from tests.integration.test_ponentes import crear_ponente
from tests.integration.test_sesiones import crear_evento, crear_sesion, cuerpo_sesion, utc

pytestmark = pytest.mark.integration


def instante(hora_bogota: str) -> datetime:
    return datetime.fromisoformat(utc(hora_bogota))


@pytest.fixture
def prefijo() -> str:
    return "rs" + uuid4().hex[:8]


@pytest.fixture
def agenda(cliente_db, conexion, prefijo) -> dict:
    """Ana de 10:00 a 11:00 en PyCon y de 13:00 a 14:00 en un evento cancelado; Beto de 12:00 a
    13:00 en PyCon."""
    token = usuario_con_rol(cliente_db, conexion, f"{prefijo}orga@mail.com", "ORGANIZER")
    pycon = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    cancelado = crear_evento(cliente_db, token, f"{prefijo} PyData")
    ana = crear_ponente(cliente_db, token, f"{prefijo} Ana Pérez")
    beto = crear_ponente(cliente_db, token, f"{prefijo} Beto Ruiz")
    de_ana = crear_sesion(cliente_db, token, pycon, cuerpo_sesion("10:00", "11:00", ana))
    assert de_ana.status_code == 201, de_ana.text
    de_beto = crear_sesion(
        cliente_db, token, pycon, cuerpo_sesion("12:00", "13:00", beto, title="Rust")
    )
    assert de_beto.status_code == 201, de_beto.text
    en_cancelado = crear_sesion(
        cliente_db, token, cancelado, cuerpo_sesion("13:00", "14:00", ana, title="Pandas")
    )
    assert en_cancelado.status_code == 201, en_cancelado.text
    cancelar = cliente_db.post(f"/events/{cancelado['id']}/cancel", headers=auth(token))
    assert cancelar.status_code == 200, cancelar.text
    return {
        "ana": UUID(ana["id"]),
        "beto": UUID(beto["id"]),
        "sesion_de_ana": UUID(de_ana.json()["id"]),
        "sesion_de_beto": UUID(de_beto.json()["id"]),
    }


@pytest.fixture
def repo(conexion) -> RepositorioSesiones:
    return RepositorioSesiones(Session(bind=conexion, join_transaction_mode="create_savepoint"))


def test_devuelve_el_ponente_la_sesion_y_su_evento_que_se_cruzan(repo, agenda, prefijo):
    choques = repo.choques_de_ponentes(
        [agenda["ana"], agenda["beto"]], instante("10:30"), instante("11:30"), None
    )

    [(ponente, sesion, evento)] = choques
    assert ponente.id == agenda["ana"]
    assert ponente.full_name == f"{prefijo} Ana Pérez"
    assert sesion.id == agenda["sesion_de_ana"]
    assert evento.id == sesion.event_id


def test_devuelve_un_choque_por_ponente_el_mas_temprano(repo, agenda):
    # De 10:30 a 12:30 Ana choca con 10:00-11:00 y Beto con 12:00-13:00.
    choques = repo.choques_de_ponentes(
        [agenda["ana"], agenda["beto"]], instante("10:30"), instante("12:30"), None
    )

    assert sorted((p.id, s.id) for p, s, _ in choques) == sorted(
        [(agenda["ana"], agenda["sesion_de_ana"]), (agenda["beto"], agenda["sesion_de_beto"])]
    )


def test_con_dos_sesiones_del_mismo_ponente_que_chocan_devuelve_la_primera(
    cliente_db, conexion, repo, agenda, prefijo
):
    token = usuario_con_rol(cliente_db, conexion, f"{prefijo}otra@mail.com", "ORGANIZER")
    otro = crear_evento(cliente_db, token, f"{prefijo} PyConES")
    ana = {"id": str(agenda["ana"])}
    despues = crear_sesion(cliente_db, token, otro, cuerpo_sesion("11:30", "12:30", ana))
    assert despues.status_code == 201, despues.text

    # De 10:30 a 12:00 se cruzan las dos de Ana: vuelve solo la que empieza antes.
    choques = repo.choques_de_ponentes([agenda["ana"]], instante("10:30"), instante("12:00"), None)

    assert [s.id for _, s, _ in choques] == [agenda["sesion_de_ana"]]


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [("11:00", "12:00"), ("09:00", "10:00"), ("08:00", "09:30"), ("11:30", "12:30")],
    ids=["empieza-cuando-termina", "termina-cuando-empieza", "antes", "despues"],
)
def test_fuera_del_rango_o_en_el_borde_no_hay_choque(repo, agenda, inicio, fin):
    choques = repo.choques_de_ponentes([agenda["ana"]], instante(inicio), instante(fin), None)

    assert choques == []


def test_la_propia_sesion_no_choca(repo, agenda):
    choques = repo.choques_de_ponentes(
        [agenda["ana"]], instante("10:00"), instante("11:00"), agenda["sesion_de_ana"]
    )

    assert choques == []


@pytest.mark.parametrize(
    ("ponente", "inicio", "fin"),
    [("ana", "12:00", "13:00"), ("beto", "10:00", "11:00")],
    ids=["ana-en-la-de-beto", "beto-en-la-de-ana"],
)
def test_la_agenda_de_otro_ponente_no_cuenta(repo, agenda, ponente, inicio, fin):
    choques = repo.choques_de_ponentes([agenda[ponente]], instante(inicio), instante(fin), None)

    assert choques == []


def test_una_sesion_de_un_evento_cancelado_no_choca(repo, agenda):
    choques = repo.choques_de_ponentes([agenda["ana"]], instante("13:00"), instante("14:00"), None)

    assert choques == []


def test_sin_ponentes_no_hay_choque(repo, agenda):
    assert repo.choques_de_ponentes([], instante("10:00"), instante("11:00"), None) == []
