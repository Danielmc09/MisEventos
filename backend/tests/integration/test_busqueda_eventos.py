"""GET /events contra PostgreSQL. La base puede traer eventos de otros lados: cada test crea
los suyos con un prefijo único y mira solo esos."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.test_eventos import auth, id_de, usuario_con_rol

pytestmark = pytest.mark.integration


@pytest.fixture
def prefijo() -> str:
    return "bq" + uuid4().hex[:8]


@pytest.fixture
def organizador(cliente_db, conexion) -> tuple[str, str]:
    """(token, id) de un organizador."""
    token = usuario_con_rol(cliente_db, conexion, "orga@mail.com", "ORGANIZER")
    return token, id_de(conexion, "orga@mail.com")


def crear_evento(
    conexion,
    organizer_id: str,
    nombre: str,
    *,
    estado: str = "PUBLISHED",
    empieza_en: timedelta = timedelta(days=10),
    dura: timedelta = timedelta(hours=2),
) -> str:
    """Directo en la base: así puede haber eventos en el pasado."""
    inicio = datetime.now(UTC) + empieza_en
    return str(
        conexion.execute(
            text(
                "INSERT INTO events (name, start_at, end_at, capacity, status, organizer_id)"
                " VALUES (:nombre, :inicio, :fin, 50, CAST(:estado AS event_status), :orga)"
                " RETURNING id"
            ),
            {
                "nombre": nombre,
                "inicio": inicio,
                "fin": inicio + dura,
                "estado": estado,
                "orga": organizer_id,
            },
        ).scalar_one()
    )


def listar(cliente, params: dict | None = None, token: str | None = None) -> dict:
    respuesta = cliente.get(
        "/events", params={"page_size": 100, **(params or {})}, headers=auth(token)
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def nombres(pagina: dict, prefijo: str) -> list[str]:
    """Los nombres de la página que son de este test, sin el prefijo, en el orden recibido."""
    return [
        e["name"].removeprefix(prefijo + " ")
        for e in pagina["items"]
        if e["name"].startswith(prefijo)
    ]


# --- Búsqueda por nombre -------------------------------------------------------------------


def test_q_busca_parte_del_nombre_sin_distinguir_mayusculas(
    cliente_db, conexion, organizador, prefijo
):
    _, orga = organizador
    for nombre in ["PyCon Bogotá", "Python Day", "Rust Conf"]:
        crear_evento(conexion, orga, f"{prefijo} {nombre}")

    assert sorted(nombres(listar(cliente_db, {"q": "py"}), prefijo)) == [
        "PyCon Bogotá",
        "Python Day",
    ]
    assert nombres(listar(cliente_db, {"q": "pyth"}), prefijo) == ["Python Day"]
    mayusculas = listar(cliente_db, {"q": "PYTHON"})
    minusculas = listar(cliente_db, {"q": "python"})
    assert nombres(mayusculas, prefijo) == nombres(minusculas, prefijo) == ["Python Day"]
    assert mayusculas["total"] == minusculas["total"]


def test_una_inyeccion_en_q_devuelve_200_sin_resultados(cliente_db, conexion, organizador, prefijo):
    _, orga = organizador
    crear_evento(conexion, orga, f"{prefijo} PyCon Bogotá")

    pagina = listar(cliente_db, {"q": "' OR 1=1 --"})

    assert nombres(listar(cliente_db, {"q": prefijo}), prefijo) == ["PyCon Bogotá"]
    assert (pagina["items"], pagina["total"], pagina["pages"]) == ([], 0, 0)


def test_q_con_porcentaje_busca_el_porcentaje_literal(cliente_db, conexion, organizador, prefijo):
    _, orga = organizador
    crear_evento(conexion, orga, f"{prefijo} Descuento 100% Python")
    crear_evento(conexion, orga, f"{prefijo} Sin comodines")
    crear_evento(conexion, orga, f"{prefijo} con_guion_bajo")

    porcentaje = listar(cliente_db, {"q": "%"})
    guion = listar(cliente_db, {"q": "_"})

    assert nombres(porcentaje, prefijo) == ["Descuento 100% Python"]
    assert all("%" in e["name"] for e in porcentaje["items"])
    assert nombres(guion, prefijo) == ["con_guion_bajo"]
    assert all("_" in e["name"] for e in guion["items"])


# --- Filtros y orden -----------------------------------------------------------------------


def test_when_separa_los_proximos_de_los_terminados(cliente_db, conexion, organizador, prefijo):
    _, orga = organizador
    crear_evento(conexion, orga, f"{prefijo} Futuro")
    crear_evento(conexion, orga, f"{prefijo} Terminado", empieza_en=timedelta(days=-3))
    crear_evento(
        conexion,
        orga,
        f"{prefijo} En curso",
        empieza_en=timedelta(hours=-1),
        dura=timedelta(hours=3),
    )

    por_defecto = listar(cliente_db, {"q": prefijo})
    proximos = listar(cliente_db, {"q": prefijo, "when": "upcoming"})
    pasados = listar(cliente_db, {"q": prefijo, "when": "past"})

    assert sorted(nombres(por_defecto, prefijo)) == ["En curso", "Futuro"]
    assert nombres(proximos, prefijo) == nombres(por_defecto, prefijo)
    assert nombres(pasados, prefijo) == ["Terminado"]
    assert pasados["items"][0]["is_finished"] is True


def test_status_filtra_por_uno_o_varios_estados(cliente_db, conexion, organizador, prefijo):
    _, orga = organizador
    crear_evento(conexion, orga, f"{prefijo} Publicado")
    crear_evento(conexion, orga, f"{prefijo} Cancelado", estado="CANCELLED")

    cancelados = listar(cliente_db, {"q": prefijo, "status": "CANCELLED"})
    ambos = listar(cliente_db, {"q": prefijo, "status": ["PUBLISHED", "CANCELLED"]})

    assert nombres(cancelados, prefijo) == ["Cancelado"]
    assert sorted(nombres(ambos, prefijo)) == ["Cancelado", "Publicado"]


def test_from_y_to_acotan_la_fecha_de_inicio(cliente_db, conexion, organizador, prefijo):
    _, orga = organizador
    for dias in (10, 20, 30):
        crear_evento(conexion, orga, f"{prefijo} Dia {dias}", empieza_en=timedelta(days=dias))
    ahora = datetime.now(UTC)
    desde = (ahora + timedelta(days=15)).isoformat()
    hasta = (ahora + timedelta(days=25)).isoformat()

    assert nombres(listar(cliente_db, {"q": prefijo, "from": desde, "to": hasta}), prefijo) == [
        "Dia 20"
    ]
    assert nombres(listar(cliente_db, {"q": prefijo, "from": desde}), prefijo) == [
        "Dia 20",
        "Dia 30",
    ]
    assert nombres(listar(cliente_db, {"q": prefijo, "to": hasta}), prefijo) == ["Dia 10", "Dia 20"]


def test_order_by_ordena_por_inicio_o_por_nombre(cliente_db, conexion, organizador, prefijo):
    _, orga = organizador
    crear_evento(conexion, orga, f"{prefijo} Beta", empieza_en=timedelta(days=10))
    crear_evento(conexion, orga, f"{prefijo} Gamma", empieza_en=timedelta(days=20))
    crear_evento(conexion, orga, f"{prefijo} Alfa", empieza_en=timedelta(days=30))

    def orden(order_by: str | None) -> list[str]:
        params = {"q": prefijo} | ({"order_by": order_by} if order_by else {})
        return nombres(listar(cliente_db, params), prefijo)

    assert orden(None) == ["Beta", "Gamma", "Alfa"]
    assert orden("start_at") == ["Beta", "Gamma", "Alfa"]
    assert orden("-start_at") == ["Alfa", "Gamma", "Beta"]
    assert orden("name") == ["Alfa", "Beta", "Gamma"]


# --- Paginación ----------------------------------------------------------------------------


def test_la_paginacion_da_total_y_paginas_y_la_ultima_trae_el_resto(
    cliente_db, conexion, organizador, prefijo
):
    _, orga = organizador
    for dias in range(1, 6):
        crear_evento(conexion, orga, f"{prefijo} Evento {dias}", empieza_en=timedelta(days=dias))

    paginas = [listar(cliente_db, {"q": prefijo, "page": n, "page_size": 2}) for n in (1, 2, 3)]

    assert [(p["total"], p["pages"], p["page"], p["page_size"]) for p in paginas] == [
        (5, 3, 1, 2),
        (5, 3, 2, 2),
        (5, 3, 3, 2),
    ]
    assert [nombres(p, prefijo) for p in paginas] == [
        ["Evento 1", "Evento 2"],
        ["Evento 3", "Evento 4"],
        ["Evento 5"],
    ]


# --- Visibilidad ---------------------------------------------------------------------------


def test_un_anonimo_no_ve_ningun_borrador_ni_pidiendolos(
    cliente_db, conexion, organizador, prefijo
):
    _, orga = organizador
    crear_evento(conexion, orga, f"{prefijo} Borrador", estado="DRAFT")
    crear_evento(conexion, orga, f"{prefijo} Publicado")

    todos = listar(cliente_db)
    borradores = listar(cliente_db, {"status": "DRAFT"})
    con_q = listar(cliente_db, {"q": prefijo, "status": ["DRAFT", "PUBLISHED"]})

    assert all(e["status"] != "DRAFT" for e in todos["items"])
    assert (borradores["items"], borradores["total"]) == ([], 0)
    assert nombres(con_q, prefijo) == ["Publicado"]


def test_un_organizador_ve_sus_borradores_y_no_los_ajenos(
    cliente_db, conexion, organizador, prefijo
):
    token, orga = organizador
    otro_token = usuario_con_rol(cliente_db, conexion, "otro@mail.com", "ORGANIZER")
    otro = id_de(conexion, "otro@mail.com")
    admin = usuario_con_rol(cliente_db, conexion, "admin@mail.com", "ADMIN")
    asistente = usuario_con_rol(cliente_db, conexion, "asis@mail.com", "ATTENDEE")
    crear_evento(conexion, orga, f"{prefijo} Mio", estado="DRAFT")
    crear_evento(conexion, otro, f"{prefijo} Ajeno", estado="DRAFT")
    crear_evento(conexion, otro, f"{prefijo} Publicado")

    def ve(quien: str) -> list[str]:
        return sorted(nombres(listar(cliente_db, {"q": prefijo}, quien), prefijo))

    assert ve(token) == ["Mio", "Publicado"]
    assert ve(otro_token) == ["Ajeno", "Publicado"]
    assert ve(asistente) == ["Publicado"]
    assert ve(admin) == ["Ajeno", "Mio", "Publicado"]
    solo_borradores = listar(cliente_db, {"q": prefijo, "status": "DRAFT"}, token)
    assert nombres(solo_borradores, prefijo) == ["Mio"]
