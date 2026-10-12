"""Inscripciones contra PostgreSQL: inscribirse con sus reglas, cancelar y volver a inscribirse."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from tests.integration.test_eventos import auth, cuerpo_valido, usuario_con_rol

pytestmark = pytest.mark.integration


@pytest.fixture
def prefijo() -> str:
    return "in" + uuid4().hex[:8]


@pytest.fixture
def usuarios(cliente_db, conexion, prefijo) -> dict[str, str]:
    """Token de cada usuario del test, por nombre."""
    roles = {"orga": "ORGANIZER", "ana": "ATTENDEE", "beto": "ATTENDEE"}
    return {
        nombre: usuario_con_rol(cliente_db, conexion, f"{prefijo}{nombre}@mail.com", rol)
        for nombre, rol in roles.items()
    }


def crear_evento(cliente, token: str, *, capacidad: int = 10, publicar: bool = True) -> str:
    cuerpo = cuerpo_valido() | {"capacity": capacidad}
    creado = cliente.post("/events", json=cuerpo, headers=auth(token))
    assert creado.status_code == 201, creado.text
    id_evento = creado.json()["id"]
    if publicar:
        publicado = cliente.post(f"/events/{id_evento}/publish", headers=auth(token))
        assert publicado.status_code == 200, publicado.text
    return id_evento


def inscribirse(cliente, token: str | None, id_evento: str):
    return cliente.post(f"/events/{id_evento}/registrations", headers=auth(token))


def cancelar(cliente, token: str | None, id_evento: str):
    return cliente.delete(f"/events/{id_evento}/registrations/me", headers=auth(token))


def empezar(conexion, id_evento: str) -> None:
    """Lo corre una hora hacia atrás: empezó hace una hora y sigue en curso."""
    conexion.execute(
        text(
            "UPDATE events SET start_at = now() - interval '1 hour',"
            " end_at = now() + interval '7 hours' WHERE id = :id"
        ),
        {"id": id_evento},
    )


def inscripciones(conexion, id_evento: str, email: str | None = None) -> list[tuple]:
    """(status, cancelled_at) de cada inscripción del evento, o solo las de ese usuario."""
    consulta = (
        "SELECT r.status, r.cancelled_at FROM registrations r JOIN users u ON u.id = r.user_id"
        " WHERE r.event_id = :e AND (CAST(:email AS text) IS NULL OR u.email = :email)"
        " ORDER BY r.created_at"
    )
    return [
        tuple(fila)
        for fila in conexion.execute(text(consulta), {"e": id_evento, "email": email}).all()
    ]


def assert_conflicto(respuesta, tipo: str) -> None:
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["type"] == tipo


# --- Inscribirse ---------------------------------------------------------------------------


def test_inscribirse_responde_201_y_el_evento_cuenta_un_inscrito_mas(
    cliente_db, conexion, usuarios, prefijo
):
    id_evento = crear_evento(cliente_db, usuarios["orga"], capacidad=10)

    respuesta = inscribirse(cliente_db, usuarios["ana"], id_evento)

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["event_id"], cuerpo["status"]) == (id_evento, "ACTIVE")
    assert inscripciones(conexion, id_evento, f"{prefijo}ana@mail.com") == [("ACTIVE", None)]
    detalle = cliente_db.get(f"/events/{id_evento}").json()
    assert (detalle["registered_count"], detalle["available_spots"]) == (1, 9)


def test_un_borrador_responde_event_not_open_y_uno_ajeno_404(cliente_db, conexion, usuarios):
    borrador = crear_evento(cliente_db, usuarios["orga"], publicar=False)

    assert_conflicto(inscribirse(cliente_db, usuarios["orga"], borrador), "event-not-open")
    ajeno = inscribirse(cliente_db, usuarios["ana"], borrador)
    assert ajeno.status_code == 404
    assert ajeno.json()["type"] == "not-found"
    assert inscripciones(conexion, borrador) == []


def test_un_evento_cancelado_responde_event_not_open(cliente_db, conexion, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    cancelado = cliente_db.post(f"/events/{id_evento}/cancel", headers=auth(usuarios["orga"]))
    assert cancelado.status_code == 200, cancelado.text

    assert_conflicto(inscribirse(cliente_db, usuarios["ana"], id_evento), "event-not-open")
    assert inscripciones(conexion, id_evento) == []


def test_un_evento_que_ya_empezo_responde_event_started(cliente_db, conexion, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    empezar(conexion, id_evento)

    assert_conflicto(inscribirse(cliente_db, usuarios["ana"], id_evento), "event-started")
    assert inscripciones(conexion, id_evento) == []


def test_inscribirse_dos_veces_responde_already_registered(cliente_db, conexion, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201

    assert_conflicto(inscribirse(cliente_db, usuarios["ana"], id_evento), "already-registered")
    assert inscripciones(conexion, id_evento) == [("ACTIVE", None)]


def test_un_evento_lleno_responde_capacity_full(cliente_db, conexion, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"], capacidad=1)
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201

    respuesta = inscribirse(cliente_db, usuarios["beto"], id_evento)

    assert_conflicto(respuesta, "capacity-full")
    assert respuesta.json()["title"] == "El evento no tiene cupos"
    assert len(inscripciones(conexion, id_evento)) == 1


def test_sin_token_responde_401(cliente_db, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"])

    assert inscribirse(cliente_db, None, id_evento).status_code == 401


def test_el_dueno_puede_inscribirse_a_su_propio_evento(cliente_db, conexion, usuarios, prefijo):
    id_evento = crear_evento(cliente_db, usuarios["orga"])

    assert inscribirse(cliente_db, usuarios["orga"], id_evento).status_code == 201
    assert inscripciones(conexion, id_evento, f"{prefijo}orga@mail.com") == [("ACTIVE", None)]


# --- Cancelar ------------------------------------------------------------------------------


def test_cancelar_responde_204_la_deja_cancelada_y_libera_el_cupo(
    cliente_db, conexion, usuarios, prefijo
):
    id_evento = crear_evento(cliente_db, usuarios["orga"], capacidad=1)
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201
    assert_conflicto(inscribirse(cliente_db, usuarios["beto"], id_evento), "capacity-full")

    respuesta = cancelar(cliente_db, usuarios["ana"], id_evento)

    assert respuesta.status_code == 204, respuesta.text
    [(estado, cancelada_en)] = inscripciones(conexion, id_evento, f"{prefijo}ana@mail.com")
    assert estado == "CANCELLED"
    assert cancelada_en is not None
    detalle = cliente_db.get(f"/events/{id_evento}").json()
    assert (detalle["registered_count"], detalle["available_spots"]) == (0, 1)
    assert inscribirse(cliente_db, usuarios["beto"], id_evento).status_code == 201


def test_volver_a_inscribirse_despues_de_cancelar_deja_una_activa_y_una_cancelada(
    cliente_db, conexion, usuarios, prefijo
):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201
    assert cancelar(cliente_db, usuarios["ana"], id_evento).status_code == 204

    respuesta = inscribirse(cliente_db, usuarios["ana"], id_evento)

    assert respuesta.status_code == 201, respuesta.text
    filas = inscripciones(conexion, id_evento, f"{prefijo}ana@mail.com")
    assert sorted(estado for estado, _ in filas) == ["ACTIVE", "CANCELLED"]


def test_cancelar_sin_inscripcion_activa_responde_404(cliente_db, conexion, usuarios, prefijo):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201

    respuesta = cancelar(cliente_db, usuarios["beto"], id_evento)

    assert respuesta.status_code == 404
    # La de otra persona no se toca: el usuario sale del token, no de la ruta.
    assert inscripciones(conexion, id_evento, f"{prefijo}ana@mail.com") == [("ACTIVE", None)]


def test_cancelar_con_el_evento_ya_empezado_responde_409(cliente_db, conexion, usuarios, prefijo):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201
    empezar(conexion, id_evento)

    assert_conflicto(cancelar(cliente_db, usuarios["ana"], id_evento), "event-started")
    assert inscripciones(conexion, id_evento, f"{prefijo}ana@mail.com") == [("ACTIVE", None)]


# --- Reglas del evento que dependen de las inscripciones -----------------------------------


def test_bajar_la_capacidad_por_debajo_de_las_activas_responde_409_e_igualarla_200(
    cliente_db, conexion, usuarios
):
    id_evento = crear_evento(cliente_db, usuarios["orga"], capacidad=5)
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201
    assert inscribirse(cliente_db, usuarios["beto"], id_evento).status_code == 201

    debajo = cliente_db.patch(
        f"/events/{id_evento}", json={"capacity": 1}, headers=auth(usuarios["orga"])
    )
    igual = cliente_db.patch(
        f"/events/{id_evento}", json={"capacity": 2}, headers=auth(usuarios["orga"])
    )

    assert_conflicto(debajo, "capacity-below-registrations")
    assert igual.status_code == 200, igual.text
    assert (igual.json()["capacity"], igual.json()["registered_count"]) == (2, 2)
    assert igual.json()["available_spots"] == 0
    capacidad = conexion.execute(
        text("SELECT capacity FROM events WHERE id = :id"), {"id": id_evento}
    ).scalar_one()
    assert capacidad == 2


def test_despublicar_o_eliminar_con_inscripciones_activas_responde_409_has_registrations(
    cliente_db, conexion, usuarios
):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201

    despublicar = cliente_db.post(f"/events/{id_evento}/unpublish", headers=auth(usuarios["orga"]))
    eliminar = cliente_db.delete(f"/events/{id_evento}", headers=auth(usuarios["orga"]))

    assert_conflicto(despublicar, "has-registrations")
    assert_conflicto(eliminar, "has-registrations")
    assert eliminar.json()["detail"] == "Cancelá el evento en lugar de eliminarlo"
    estado = conexion.execute(
        text("SELECT status FROM events WHERE id = :id"), {"id": id_evento}
    ).scalar_one()
    assert estado == "PUBLISHED"
    assert inscripciones(conexion, id_evento) == [("ACTIVE", None)]


def test_cancelar_un_evento_con_inscripciones_responde_200_y_las_conserva_activas(
    cliente_db, conexion, usuarios
):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201
    assert inscribirse(cliente_db, usuarios["beto"], id_evento).status_code == 201

    respuesta = cliente_db.post(f"/events/{id_evento}/cancel", headers=auth(usuarios["orga"]))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["status"] == "CANCELLED"
    assert respuesta.json()["registered_count"] == 2
    assert inscripciones(conexion, id_evento) == [("ACTIVE", None), ("ACTIVE", None)]


# --- Conteos e is_registered ----------------------------------------------------------------


def test_el_detalle_dice_is_registered_true_al_inscrito_y_false_a_otro(cliente_db, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201

    def inscrito(token: str | None) -> bool:
        respuesta = cliente_db.get(f"/events/{id_evento}", headers=auth(token))
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()["is_registered"]

    assert inscrito(usuarios["ana"]) is True
    assert inscrito(usuarios["beto"]) is False
    assert inscrito(None) is False


@contextmanager
def contar_consultas(conexion) -> Iterator[list[str]]:
    """Junta cada sentencia que pasa por la conexión del test mientras dura el bloque."""
    sentencias: list[str] = []

    def registrar(_conn, _cursor, sentencia, *_args) -> None:
        sentencias.append(sentencia)

    event.listen(conexion, "before_cursor_execute", registrar)
    try:
        yield sentencias
    finally:
        event.remove(conexion, "before_cursor_execute", registrar)


def test_el_listado_cuenta_los_inscritos_con_una_cantidad_fija_de_consultas(
    cliente_db, conexion, usuarios, prefijo
):
    ids = []
    for numero in range(12):
        cuerpo = cuerpo_valido() | {"name": f"{prefijo} evento {numero:02d}", "capacity": 5}
        creado = cliente_db.post("/events", json=cuerpo, headers=auth(usuarios["orga"]))
        assert creado.status_code == 201, creado.text
        ids.append(creado.json()["id"])
        publicado = cliente_db.post(f"/events/{ids[-1]}/publish", headers=auth(usuarios["orga"]))
        assert publicado.status_code == 200, publicado.text
    for id_evento in ids[:3]:
        assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201
    assert inscribirse(cliente_db, usuarios["beto"], ids[0]).status_code == 201

    def listar(cuantos: int):
        with contar_consultas(conexion) as sentencias:
            respuesta = cliente_db.get(
                "/events", params={"q": prefijo, "page_size": cuantos, "order_by": "name"}
            )
        assert respuesta.status_code == 200, respuesta.text
        assert len(respuesta.json()["items"]) == cuantos
        return respuesta.json()["items"], len(sentencias)

    doce, consultas_con_doce = listar(12)
    _, consultas_con_dos = listar(2)

    assert consultas_con_doce == consultas_con_dos
    conteos = {e["id"]: (e["registered_count"], e["available_spots"]) for e in doce}
    assert conteos[ids[0]] == (2, 3)
    assert conteos[ids[1]] == conteos[ids[2]] == (1, 4)
    assert all(conteos[id_evento] == (0, 5) for id_evento in ids[3:])


# --- Mis inscripciones ----------------------------------------------------------------------


def terminar(conexion, id_evento: str) -> None:
    conexion.execute(
        text(
            "UPDATE events SET start_at = now() - interval '2 days',"
            " end_at = now() - interval '1 day' WHERE id = :id"
        ),
        {"id": id_evento},
    )


def mias(cliente, token: str, **params) -> list[tuple[str, str, str]]:
    """(event_id, status de la inscripción, status del evento) de cada una, en orden."""
    respuesta = cliente.get("/me/registrations", headers=auth(token), params=params)
    assert respuesta.status_code == 200, respuesta.text
    return [(i["event_id"], i["status"], i["event"]["status"]) for i in respuesta.json()["items"]]


def test_mis_inscripciones_trae_solo_las_del_usuario_y_filtra_por_status_y_when(
    cliente_db, conexion, usuarios
):
    proximo = crear_evento(cliente_db, usuarios["orga"])
    cancelada = crear_evento(cliente_db, usuarios["orga"])
    pasado = crear_evento(cliente_db, usuarios["orga"])
    cancelado_por_el_organizador = crear_evento(cliente_db, usuarios["orga"])
    solo_de_beto = crear_evento(cliente_db, usuarios["orga"])
    for id_evento in (proximo, cancelada, pasado, cancelado_por_el_organizador):
        assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201
    for id_evento in (proximo, solo_de_beto):
        assert inscribirse(cliente_db, usuarios["beto"], id_evento).status_code == 201
    assert cancelar(cliente_db, usuarios["ana"], cancelada).status_code == 204
    cancelado = cliente_db.post(
        f"/events/{cancelado_por_el_organizador}/cancel", headers=auth(usuarios["orga"])
    )
    assert cancelado.status_code == 200, cancelado.text
    terminar(conexion, pasado)

    por_defecto = mias(cliente_db, usuarios["ana"])
    canceladas = mias(cliente_db, usuarios["ana"], status="CANCELLED")
    pasadas = mias(cliente_db, usuarios["ana"], when="past")
    canceladas_pasadas = mias(cliente_db, usuarios["ana"], status="CANCELLED", when="past")

    assert sorted(por_defecto) == sorted(
        [
            (proximo, "ACTIVE", "PUBLISHED"),
            (cancelado_por_el_organizador, "ACTIVE", "CANCELLED"),
        ]
    )
    assert canceladas == [(cancelada, "CANCELLED", "PUBLISHED")]
    assert pasadas == [(pasado, "ACTIVE", "PUBLISHED")]
    assert canceladas_pasadas == []
    assert sorted(mias(cliente_db, usuarios["beto"])) == sorted(
        [(proximo, "ACTIVE", "PUBLISHED"), (solo_de_beto, "ACTIVE", "PUBLISHED")]
    )


def test_mis_inscripciones_trae_el_resumen_del_evento(cliente_db, conexion, usuarios):
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201
    detalle = cliente_db.get(f"/events/{id_evento}").json()

    respuesta = cliente_db.get("/me/registrations", headers=auth(usuarios["ana"]))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["total"] == 1
    [item] = respuesta.json()["items"]
    assert item["event"] == {
        "id": id_evento,
        "name": detalle["name"],
        "start_at": detalle["start_at"],
        "location": detalle["location"],
        "status": "PUBLISHED",
        "is_finished": False,
    }


# --- Inscritos y estadísticas del evento ------------------------------------------------------


@pytest.mark.parametrize("recurso", ["registrations", "stats"])
def test_inscritos_y_estadisticas_dueno_200_admin_200_otro_403_y_borrador_ajeno_404(
    cliente_db, conexion, usuarios, prefijo, recurso
):
    admin = usuario_con_rol(cliente_db, conexion, f"{prefijo}admin@mail.com", "ADMIN")
    id_evento = crear_evento(cliente_db, usuarios["orga"])
    borrador = crear_evento(cliente_db, usuarios["orga"], publicar=False)
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201

    def pedir(token: str | None, evento: str = id_evento) -> int:
        return cliente_db.get(f"/events/{evento}/{recurso}", headers=auth(token)).status_code

    assert pedir(usuarios["orga"]) == 200
    assert pedir(admin) == 200
    assert pedir(usuarios["ana"]) == 403
    assert pedir(usuarios["beto"]) == 403
    assert pedir(usuarios["beto"], borrador) == 404
    assert pedir(None) == 401


def test_las_estadisticas_y_la_lista_de_inscritos_reflejan_la_base(
    cliente_db, conexion, usuarios, prefijo
):
    id_evento = crear_evento(cliente_db, usuarios["orga"], capacidad=3)
    assert inscribirse(cliente_db, usuarios["ana"], id_evento).status_code == 201
    assert inscribirse(cliente_db, usuarios["beto"], id_evento).status_code == 201
    assert cancelar(cliente_db, usuarios["beto"], id_evento).status_code == 204

    estadisticas = cliente_db.get(f"/events/{id_evento}/stats", headers=auth(usuarios["orga"]))
    lista = cliente_db.get(f"/events/{id_evento}/registrations", headers=auth(usuarios["orga"]))

    assert estadisticas.status_code == 200, estadisticas.text
    assert estadisticas.json() == {
        "active": 1,
        "cancelled": 1,
        "capacity": 3,
        "available_spots": 2,
        "occupancy_pct": 33.3,
        "sessions": [],
    }
    assert lista.status_code == 200, lista.text
    assert lista.json()["total"] == 2
    assert sorted((i["email"], i["status"]) for i in lista.json()["items"]) == [
        (f"{prefijo}ana@mail.com", "ACTIVE"),
        (f"{prefijo}beto@mail.com", "CANCELLED"),
    ]
