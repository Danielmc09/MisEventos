"""Sesiones contra PostgreSQL: alta con ponentes, listado público, permisos y borrados."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.test_eventos import auth, usuario_con_rol
from tests.integration.test_ponentes import crear_ponente

pytestmark = pytest.mark.integration

# El evento va de 8:00 a 18:00 en Bogotá (13:00 a 23:00 UTC).
INICIO_EVENTO = "2030-01-10T13:00:00Z"
FIN_EVENTO = "2030-01-10T23:00:00Z"


@pytest.fixture
def prefijo() -> str:
    return "se" + uuid4().hex[:8]


@pytest.fixture
def usuarios(cliente_db, conexion, prefijo) -> dict[str, str]:
    """Token de cada usuario del test, por nombre."""
    roles = {"orga": "ORGANIZER", "otro": "ORGANIZER", "admin": "ADMIN"}
    return {
        nombre: usuario_con_rol(cliente_db, conexion, f"{prefijo}{nombre}@mail.com", rol)
        for nombre, rol in roles.items()
    }


def crear_evento(
    cliente, token: str, nombre: str, *, publicar: bool = True, inicio=INICIO_EVENTO, fin=FIN_EVENTO
) -> dict:
    cuerpo = {"name": nombre, "start_at": inicio, "end_at": fin, "capacity": 100}
    respuesta = cliente.post("/events", json=cuerpo, headers=auth(token))
    assert respuesta.status_code == 201, respuesta.text
    evento = respuesta.json()
    if publicar:
        publicado = cliente.post(f"/events/{evento['id']}/publish", headers=auth(token))
        assert publicado.status_code == 200, publicado.text
    return evento


def utc(hora_bogota: str) -> str:
    """'10:00' en Bogotá → la fecha del evento en UTC."""
    horas, minutos = hora_bogota.split(":")
    return f"2030-01-10T{int(horas) + 5:02d}:{minutos}:00Z"


def cuerpo_sesion(inicio: str = "10:00", fin: str = "11:00", *ponentes: dict, **cambios) -> dict:
    datos = {
        "title": "Testing en Python",
        "start_at": utc(inicio),
        "end_at": utc(fin),
        "speaker_ids": [p["id"] for p in ponentes],
    }
    return datos | cambios


def crear_sesion(cliente, token: str | None, evento: dict, datos: dict):
    return cliente.post(f"/events/{evento['id']}/sessions", json=datos, headers=auth(token))


def contar(conexion, tabla: str, id_evento: str) -> int:
    consultas = {
        "sessions": "SELECT count(*) FROM sessions WHERE event_id = :id",
        "session_speakers": (
            "SELECT count(*) FROM session_speakers ss"
            " JOIN sessions s ON s.id = ss.session_id WHERE s.event_id = :id"
        ),
    }
    return conexion.execute(text(consultas[tabla]), {"id": id_evento}).scalar_one()


def test_una_sesion_con_dos_ponentes_guarda_los_dos_y_el_listado_no_muestra_emails(
    cliente_db, conexion, usuarios, prefijo
):
    token = usuarios["orga"]
    evento = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    ana = crear_ponente(cliente_db, token, f"{prefijo} Ana Pérez", "ana@mail.com")
    beto = crear_ponente(cliente_db, token, f"{prefijo} Beto Ruiz", "beto@mail.com")

    creada = crear_sesion(cliente_db, token, evento, cuerpo_sesion("10:00", "11:00", ana, beto))

    assert creada.status_code == 201, creada.text
    assert contar(conexion, "session_speakers", evento["id"]) == 2
    listado = cliente_db.get(f"/events/{evento['id']}/sessions")
    assert listado.status_code == 200, listado.text
    [sesion] = listado.json()
    assert sorted(p["full_name"] for p in sesion["speakers"]) == [
        f"{prefijo} Ana Pérez",
        f"{prefijo} Beto Ruiz",
    ]
    assert all("email" not in p for p in sesion["speakers"])
    assert "mail.com" not in listado.text


def test_el_listado_ordena_por_hora_de_inicio(cliente_db, usuarios, prefijo):
    token = usuarios["orga"]
    evento = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    for inicio, fin, titulo in [("14:00", "15:00", "Tarde"), ("09:00", "10:00", "Mañana")]:
        respuesta = crear_sesion(
            cliente_db, token, evento, cuerpo_sesion(inicio, fin, title=titulo)
        )
        assert respuesta.status_code == 201, respuesta.text

    listado = cliente_db.get(f"/events/{evento['id']}/sessions")

    assert listado.status_code == 200
    assert [s["title"] for s in listado.json()] == ["Mañana", "Tarde"]


def test_otro_organizador_no_crea_sesiones_en_un_evento_ajeno_y_el_admin_si(
    cliente_db, usuarios, prefijo
):
    evento = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} PyCon")

    ajeno = crear_sesion(cliente_db, usuarios["otro"], evento, cuerpo_sesion())
    admin = crear_sesion(cliente_db, usuarios["admin"], evento, cuerpo_sesion())

    assert ajeno.status_code == 403
    assert ajeno.json()["type"] == "forbidden"
    assert admin.status_code == 201, admin.text


def test_las_sesiones_de_un_borrador_ajeno_son_404_para_un_anonimo(cliente_db, usuarios, prefijo):
    borrador = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} PyCon", publicar=False)
    creada = crear_sesion(cliente_db, usuarios["orga"], borrador, cuerpo_sesion())
    assert creada.status_code == 201, creada.text

    anonimo = cliente_db.get(f"/events/{borrador['id']}/sessions")
    dueno = cliente_db.get(f"/events/{borrador['id']}/sessions", headers=auth(usuarios["orga"]))

    assert anonimo.status_code == 404
    assert anonimo.json()["type"] == "not-found"
    assert dueno.status_code == 200
    assert len(dueno.json()) == 1


def test_sin_token_no_se_crea_una_sesion(cliente_db, conexion, usuarios, prefijo):
    evento = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} PyCon")

    respuesta = crear_sesion(cliente_db, None, evento, cuerpo_sesion())

    assert respuesta.status_code == 401
    assert contar(conexion, "sessions", evento["id"]) == 0


def test_eliminar_un_ponente_con_sesiones_creadas_por_la_api_responde_409(
    cliente_db, conexion, usuarios, prefijo
):
    token = usuarios["orga"]
    evento = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    ana = crear_ponente(cliente_db, token, f"{prefijo} Ana Pérez")
    creada = crear_sesion(cliente_db, token, evento, cuerpo_sesion("10:00", "11:00", ana))
    assert creada.status_code == 201, creada.text

    respuesta = cliente_db.delete(f"/speakers/{ana['id']}", headers=auth(token))

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "speaker-has-sessions"
    assert (
        conexion.execute(
            text("SELECT count(*) FROM speakers WHERE id = :id"), {"id": ana["id"]}
        ).scalar_one()
        == 1
    )


def test_eliminar_el_evento_elimina_sus_sesiones(cliente_db, conexion, usuarios, prefijo):
    token = usuarios["orga"]
    evento = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    ana = crear_ponente(cliente_db, token, f"{prefijo} Ana Pérez")
    for inicio, fin in [("09:00", "10:00"), ("10:00", "11:00")]:
        creada = crear_sesion(cliente_db, token, evento, cuerpo_sesion(inicio, fin, ana))
        assert creada.status_code == 201, creada.text
    assert contar(conexion, "sessions", evento["id"]) == 2

    respuesta = cliente_db.delete(f"/events/{evento['id']}", headers=auth(token))

    assert respuesta.status_code == 204
    assert contar(conexion, "sessions", evento["id"]) == 0
    assert contar(conexion, "session_speakers", evento["id"]) == 0
    # El ponente sigue: es global y ya no tiene sesiones.
    assert cliente_db.delete(f"/speakers/{ana['id']}", headers=auth(token)).status_code == 204


def test_editar_y_eliminar_una_sesion(cliente_db, conexion, usuarios, prefijo):
    token = usuarios["orga"]
    evento = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    ana = crear_ponente(cliente_db, token, f"{prefijo} Ana Pérez")
    creada = crear_sesion(cliente_db, token, evento, cuerpo_sesion("10:00", "11:00", ana))
    assert creada.status_code == 201, creada.text
    id_sesion = creada.json()["id"]

    editada = cliente_db.patch(
        f"/sessions/{id_sesion}",
        json={"title": "Pytest avanzado", "speaker_ids": []},
        headers=auth(token),
    )
    assert editada.status_code == 200, editada.text
    assert (editada.json()["title"], editada.json()["speakers"]) == ("Pytest avanzado", [])
    assert contar(conexion, "session_speakers", evento["id"]) == 0

    eliminada = cliente_db.delete(f"/sessions/{id_sesion}", headers=auth(token))
    assert eliminada.status_code == 204
    assert contar(conexion, "sessions", evento["id"]) == 0


# --- Reglas de horario ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [("07:59", "09:00"), ("17:00", "18:01")],
    ids=["empieza-antes", "termina-despues"],
)
def test_una_sesion_fuera_del_evento_responde_409(cliente_db, usuarios, prefijo, inicio, fin):
    evento = crear_evento(cliente_db, usuarios["orga"], f"{prefijo} PyCon")

    respuesta = crear_sesion(cliente_db, usuarios["orga"], evento, cuerpo_sesion(inicio, fin))

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "session-outside-event"


def test_el_mismo_ponente_en_sesiones_que_se_cruzan_en_eventos_distintos_responde_409(
    cliente_db, usuarios, prefijo
):
    token = usuarios["orga"]
    pycon = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    rustconf = crear_evento(cliente_db, usuarios["admin"], f"{prefijo} RustConf")
    ana = crear_ponente(cliente_db, token, f"{prefijo} Ana Pérez")
    primera = crear_sesion(cliente_db, token, pycon, cuerpo_sesion("10:00", "11:00", ana))
    assert primera.status_code == 201, primera.text

    choque = crear_sesion(
        cliente_db,
        usuarios["admin"],
        rustconf,
        cuerpo_sesion("10:30", "11:30", ana, title="Rust para pythonistas"),
    )

    assert choque.status_code == 409
    assert choque.json()["type"] == "speaker-conflict"
    assert choque.json()["detail"] == (
        f"{prefijo} Ana Pérez ya está en «Testing en Python», 10:00 a 11:00"
    )


def test_una_sesion_de_un_evento_cancelado_no_ocupa_al_ponente(cliente_db, usuarios, prefijo):
    token = usuarios["orga"]
    cancelado = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    otro = crear_evento(cliente_db, token, f"{prefijo} PyData")
    ana = crear_ponente(cliente_db, token, f"{prefijo} Ana Pérez")
    primera = crear_sesion(cliente_db, token, cancelado, cuerpo_sesion("10:00", "11:00", ana))
    assert primera.status_code == 201, primera.text
    cancelar = cliente_db.post(f"/events/{cancelado['id']}/cancel", headers=auth(token))
    assert cancelar.status_code == 200, cancelar.text

    respuesta = crear_sesion(cliente_db, token, otro, cuerpo_sesion("10:00", "11:00", ana))

    assert respuesta.status_code == 201, respuesta.text


def test_la_misma_sala_escrita_distinto_que_se_cruza_responde_409(cliente_db, usuarios, prefijo):
    token = usuarios["orga"]
    evento = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    primera = crear_sesion(cliente_db, token, evento, cuerpo_sesion(room="Sala B"))
    assert primera.status_code == 201, primera.text

    choque = crear_sesion(
        cliente_db, token, evento, cuerpo_sesion("10:30", "11:30", room=" sala b ")
    )

    assert choque.status_code == 409
    assert choque.json()["type"] == "room-conflict"


@pytest.mark.parametrize(
    "salas", [("Sala A", "Sala B"), (None, None)], ids=["salas-distintas", "sin-sala"]
)
def test_sesiones_que_se_cruzan_sin_compartir_sala_se_aceptan(
    cliente_db, conexion, usuarios, prefijo, salas
):
    token = usuarios["orga"]
    evento = crear_evento(cliente_db, token, f"{prefijo} PyCon")

    respuestas = [
        crear_sesion(cliente_db, token, evento, cuerpo_sesion("10:00", "11:00", room=sala))
        for sala in salas
    ]

    assert [r.status_code for r in respuestas] == [201, 201]
    assert contar(conexion, "sessions", evento["id"]) == 2


def test_crear_o_editar_una_sesion_de_un_evento_cancelado_responde_409(
    cliente_db, conexion, usuarios, prefijo
):
    token = usuarios["orga"]
    evento = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    creada = crear_sesion(cliente_db, token, evento, cuerpo_sesion())
    assert creada.status_code == 201, creada.text
    cancelar = cliente_db.post(f"/events/{evento['id']}/cancel", headers=auth(token))
    assert cancelar.status_code == 200, cancelar.text

    nueva = crear_sesion(cliente_db, token, evento, cuerpo_sesion("14:00", "15:00"))
    edicion = cliente_db.patch(
        f"/sessions/{creada.json()['id']}", json={"title": "Otro título"}, headers=auth(token)
    )

    assert (nueva.status_code, edicion.status_code) == (409, 409)
    assert contar(conexion, "sessions", evento["id"]) == 1
    titulo = conexion.execute(
        text("SELECT title FROM sessions WHERE id = :id"), {"id": creada.json()["id"]}
    ).scalar_one()
    assert titulo == "Testing en Python"


def test_achicar_las_fechas_del_evento_dejando_una_sesion_afuera_responde_409(
    cliente_db, conexion, usuarios, prefijo
):
    token = usuarios["orga"]
    evento = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    creada = crear_sesion(cliente_db, token, evento, cuerpo_sesion("16:00", "17:00"))
    assert creada.status_code == 201, creada.text

    respuesta = cliente_db.patch(
        f"/events/{evento['id']}", json={"end_at": utc("16:30")}, headers=auth(token)
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "sessions-outside-range"
    assert respuesta.json()["detail"].startswith("1 ")
    fin = conexion.execute(
        text("SELECT end_at FROM events WHERE id = :id"), {"id": evento["id"]}
    ).scalar_one()
    assert fin == datetime(2030, 1, 10, 23, tzinfo=UTC)


def test_bajar_la_capacidad_del_evento_por_debajo_de_una_sesion_responde_409(
    cliente_db, conexion, usuarios, prefijo
):
    token = usuarios["orga"]
    evento = crear_evento(cliente_db, token, f"{prefijo} PyCon")
    grande = crear_sesion(cliente_db, token, evento, cuerpo_sesion("10:00", "11:00", capacity=80))
    sin_capacidad = crear_sesion(cliente_db, token, evento, cuerpo_sesion("12:00", "13:00"))
    assert (grande.status_code, sin_capacidad.status_code) == (201, 201)

    rechazada = cliente_db.patch(
        f"/events/{evento['id']}", json={"capacity": 50}, headers=auth(token)
    )
    capacidad = conexion.execute(
        text("SELECT capacity FROM events WHERE id = :id"), {"id": evento["id"]}
    ).scalar_one()
    aceptada = cliente_db.patch(
        f"/events/{evento['id']}", json={"capacity": 80}, headers=auth(token)
    )

    assert rechazada.status_code == 409
    assert rechazada.json()["type"] == "sessions-capacity-above"
    assert rechazada.json()["detail"] == "1 sesión tiene más capacidad que la nueva"
    assert capacidad == 100
    assert aceptada.status_code == 200, aceptada.text
    assert aceptada.json()["capacity"] == 80
