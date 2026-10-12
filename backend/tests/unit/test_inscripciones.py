"""Inscripciones a un evento: las reglas de inscribirse, en su orden, y cancelar la propia."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.api.dependencias import (
    repositorio_eventos,
    repositorio_inscripciones,
    repositorio_usuarios,
)
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import EstadoInscripcion, Registration
from app.models.usuario import User
from app.services.inscripciones import porcentaje_de_ocupacion
from tests.unit.dobles import (
    RepositorioEventosFalso,
    RepositorioInscripcionesFalso,
    RepositorioUsuariosFalso,
)

ASISTENTE = User(email="asistente@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
OTRO_ASISTENTE = User(email="otro@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
ORGANIZADOR = User(email="orga@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
ADMIN = User(email="admin@mail.com", password_hash="$argon2id$x", role=Rol.ADMIN)


class Repos:
    def __init__(self) -> None:
        self.usuarios = RepositorioUsuariosFalso(ASISTENTE, OTRO_ASISTENTE, ORGANIZADOR, ADMIN)
        self.eventos = RepositorioEventosFalso()
        self.inscripciones = RepositorioInscripcionesFalso(self.eventos, self.usuarios)

    def evento(
        self, estado: EstadoEvento = EstadoEvento.PUBLISHED, *, empezado: bool = False, **cambios
    ) -> Event:
        inicio = datetime.now(UTC) + (timedelta(hours=-1) if empezado else timedelta(days=30))
        datos = {
            "name": "PyCon Bogotá",
            "start_at": inicio,
            "end_at": inicio + timedelta(hours=8),
            "capacity": 50,
            "status": estado,
            "organizer_id": ORGANIZADOR.id,
        } | cambios
        return self.eventos.crear(Event(**datos))

    def inscribir(
        self, usuario: User, evento: Event, estado: EstadoInscripcion = EstadoInscripcion.ACTIVE
    ) -> Registration:
        return self.inscripciones.crear(
            Registration(user_id=usuario.id, event_id=evento.id, status=estado)
        )

    def de(self, usuario: User, evento: Event) -> list[Registration]:
        return [
            i
            for i in self.eventos.inscripciones.values()
            if i.user_id == usuario.id and i.event_id == evento.id
        ]


@pytest.fixture
def repos(app) -> Repos:
    nuevos = Repos()
    app.dependency_overrides[repositorio_usuarios] = lambda: nuevos.usuarios
    app.dependency_overrides[repositorio_eventos] = lambda: nuevos.eventos
    app.dependency_overrides[repositorio_inscripciones] = lambda: nuevos.inscripciones
    return nuevos


@pytest.fixture
def auth(settings):
    def de(usuario: User | None) -> dict:
        if usuario is None:
            return {}
        return {"Authorization": f"Bearer {crear_access_token(usuario.id, settings.jwt_secret, 5)}"}

    return de


def inscribirse(cliente, evento: Event, headers: dict, **kwargs):
    return cliente.post(f"/events/{evento.id}/registrations", headers=headers, **kwargs)


def lleno(repos: Repos, evento: Event) -> None:
    """Ocupa todos los cupos con inscripciones de otras personas."""
    for _ in range(evento.capacity):
        otro = User(email="x@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
        repos.inscribir(otro, evento)


def assert_conflicto(respuesta, tipo: str) -> None:
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo["type"] == tipo
    assert cuerpo["title"]
    assert cuerpo.get("detail"), "el 409 explica en el detalle qué pasó"
    assert cuerpo["detail"] != cuerpo["title"]
    assert cuerpo["trace_id"]


# --- Inscribirse ---------------------------------------------------------------------------


def test_inscribirse_a_un_evento_publicado_con_cupo_responde_201(cliente, repos, auth):
    evento = repos.evento()

    respuesta = inscribirse(cliente, evento, auth(ASISTENTE))

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "event_id", "status", "created_at"}
    assert cuerpo["event_id"] == str(evento.id)
    assert cuerpo["status"] == "ACTIVE"
    assert cuerpo["created_at"].endswith("Z")
    [guardada] = repos.de(ASISTENTE, evento)
    assert str(guardada.id) == cuerpo["id"]
    assert guardada.status == EstadoInscripcion.ACTIVE


def test_inscribirse_bloquea_la_fila_del_evento(cliente, repos, auth):
    evento = repos.evento()

    inscribirse(cliente, evento, auth(ASISTENTE))

    assert repos.eventos.bloqueos == [evento.id]


def test_un_borrador_lleno_responde_event_not_open_y_no_capacity_full(cliente, repos, auth):
    # El dueño ve su borrador, así que no corta en 404: llega a las reglas de estado y cupo.
    borrador = repos.evento(EstadoEvento.DRAFT, capacity=2)
    lleno(repos, borrador)

    respuesta = inscribirse(cliente, borrador, auth(ORGANIZADOR))

    assert_conflicto(respuesta, "event-not-open")
    assert repos.de(ORGANIZADOR, borrador) == []


def test_un_evento_cancelado_responde_event_not_open(cliente, repos, auth):
    evento = repos.evento(EstadoEvento.CANCELLED)

    assert_conflicto(inscribirse(cliente, evento, auth(ASISTENTE)), "event-not-open")


def test_un_evento_que_ya_empezo_responde_event_started_aunque_este_lleno(cliente, repos, auth):
    evento = repos.evento(empezado=True, capacity=1)
    lleno(repos, evento)

    assert_conflicto(inscribirse(cliente, evento, auth(ASISTENTE)), "event-started")


def test_inscribirse_dos_veces_responde_already_registered_aunque_este_lleno(cliente, repos, auth):
    evento = repos.evento(capacity=1)
    repos.inscribir(ASISTENTE, evento)

    respuesta = inscribirse(cliente, evento, auth(ASISTENTE))

    assert_conflicto(respuesta, "already-registered")
    assert len(repos.de(ASISTENTE, evento)) == 1


def test_un_evento_lleno_responde_capacity_full_con_la_capacidad_en_el_detalle(
    cliente, repos, auth
):
    evento = repos.evento(capacity=3)
    lleno(repos, evento)

    respuesta = inscribirse(cliente, evento, auth(ASISTENTE))

    assert_conflicto(respuesta, "capacity-full")
    assert respuesta.json()["title"] == "El evento no tiene cupos"
    assert "3" in respuesta.json()["detail"]
    assert repos.de(ASISTENTE, evento) == []


def test_las_canceladas_no_ocupan_cupo(cliente, repos, auth):
    evento = repos.evento(capacity=1)
    repos.inscribir(OTRO_ASISTENTE, evento, EstadoInscripcion.CANCELLED)

    assert inscribirse(cliente, evento, auth(ASISTENTE)).status_code == 201


def test_el_ultimo_cupo_entra(cliente, repos, auth):
    evento = repos.evento(capacity=2)
    repos.inscribir(OTRO_ASISTENTE, evento)

    assert inscribirse(cliente, evento, auth(ASISTENTE)).status_code == 201


def test_un_borrador_ajeno_responde_404(cliente, repos, auth):
    borrador = repos.evento(EstadoEvento.DRAFT)

    respuesta = inscribirse(cliente, borrador, auth(ASISTENTE))

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "not-found"


def test_un_evento_que_no_existe_responde_404(cliente, repos, auth):
    fantasma = Event(
        name="No existe",
        start_at=datetime.now(UTC),
        end_at=datetime.now(UTC),
        capacity=1,
        organizer_id=ORGANIZADOR.id,
    )

    assert inscribirse(cliente, fantasma, auth(ASISTENTE)).status_code == 404


def test_sin_token_responde_401(cliente, repos):
    evento = repos.evento()

    respuesta = inscribirse(cliente, evento, {})

    assert respuesta.status_code == 401
    assert repos.eventos.inscripciones == {}


def test_un_campo_desconocido_en_el_cuerpo_responde_422(cliente, repos, auth):
    evento = repos.evento()

    respuesta = inscribirse(cliente, evento, auth(ASISTENTE), json={"confirm_overlap": True})

    assert respuesta.status_code == 422
    assert respuesta.json()["errors"][0]["field"] == "confirm_overlap"
    assert repos.eventos.inscripciones == {}


def test_un_cuerpo_vacio_se_acepta(cliente, repos, auth):
    evento = repos.evento()

    assert inscribirse(cliente, evento, auth(ASISTENTE), json={}).status_code == 201


# --- Cancelar ------------------------------------------------------------------------------


def cancelar(cliente, evento: Event, headers: dict):
    return cliente.delete(f"/events/{evento.id}/registrations/me", headers=headers)


def test_cancelar_la_propia_responde_204_y_la_deja_cancelada_con_fecha(cliente, repos, auth):
    evento = repos.evento()
    inscripcion = repos.inscribir(ASISTENTE, evento)
    antes = datetime.now(UTC)

    respuesta = cancelar(cliente, evento, auth(ASISTENTE))

    assert respuesta.status_code == 204, respuesta.text
    assert respuesta.content == b""
    assert inscripcion.status == EstadoInscripcion.CANCELLED
    assert inscripcion.cancelled_at is not None
    assert inscripcion.cancelled_at >= antes
    assert repos.eventos.bloqueos == [evento.id]


def test_cancelar_libera_el_cupo(cliente, repos, auth):
    evento = repos.evento(capacity=1)
    repos.inscribir(ASISTENTE, evento)
    assert_conflicto(inscribirse(cliente, evento, auth(OTRO_ASISTENTE)), "capacity-full")

    assert cancelar(cliente, evento, auth(ASISTENTE)).status_code == 204

    assert inscribirse(cliente, evento, auth(OTRO_ASISTENTE)).status_code == 201


def test_volver_a_inscribirse_despues_de_cancelar_deja_una_activa_y_una_cancelada(
    cliente, repos, auth
):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento)
    assert cancelar(cliente, evento, auth(ASISTENTE)).status_code == 204

    respuesta = inscribirse(cliente, evento, auth(ASISTENTE))

    assert respuesta.status_code == 201, respuesta.text
    estados = sorted(i.status for i in repos.de(ASISTENTE, evento))
    assert estados == [EstadoInscripcion.ACTIVE, EstadoInscripcion.CANCELLED]


def test_cancelar_sin_inscripcion_activa_responde_404(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento, EstadoInscripcion.CANCELLED)

    respuesta = cancelar(cliente, evento, auth(ASISTENTE))

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "not-found"


def test_cancelar_solo_toca_la_inscripcion_del_usuario_del_token(cliente, repos, auth):
    evento = repos.evento()
    ajena = repos.inscribir(ASISTENTE, evento)

    assert cancelar(cliente, evento, auth(OTRO_ASISTENTE)).status_code == 404

    assert ajena.status == EstadoInscripcion.ACTIVE
    assert ajena.cancelled_at is None


def test_cancelar_con_el_evento_ya_empezado_responde_event_started(cliente, repos, auth):
    evento = repos.evento(empezado=True)
    inscripcion = repos.inscribir(ASISTENTE, evento)

    respuesta = cancelar(cliente, evento, auth(ASISTENTE))

    assert_conflicto(respuesta, "event-started")
    assert inscripcion.status == EstadoInscripcion.ACTIVE
    assert inscripcion.cancelled_at is None


def test_cancelar_en_un_evento_que_no_existe_responde_404(cliente, repos, auth):
    fantasma = repos.evento()
    del repos.eventos.eventos[fantasma.id]

    assert cancelar(cliente, fantasma, auth(ASISTENTE)).status_code == 404


def test_cancelar_sin_token_responde_401(cliente, repos):
    evento = repos.evento()
    inscripcion = repos.inscribir(ASISTENTE, evento)

    assert cancelar(cliente, evento, {}).status_code == 401
    assert inscripcion.status == EstadoInscripcion.ACTIVE


# --- El evento cuenta sus inscritos --------------------------------------------------------


def test_el_detalle_del_evento_cuenta_solo_las_inscripciones_activas(cliente, repos, auth):
    evento = repos.evento(capacity=5)
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento)
    repos.inscribir(ORGANIZADOR, evento, EstadoInscripcion.CANCELLED)
    otro_evento = repos.evento()
    repos.inscribir(ASISTENTE, otro_evento)

    cuerpo = cliente.get(f"/events/{evento.id}").json()

    assert (cuerpo["registered_count"], cuerpo["available_spots"]) == (2, 3)


def test_inscribirse_y_cancelar_se_ven_en_el_detalle_del_evento(cliente, repos, auth):
    evento = repos.evento(capacity=5)

    assert inscribirse(cliente, evento, auth(ASISTENTE)).status_code == 201
    despues_de_inscribirse = cliente.get(f"/events/{evento.id}").json()
    assert cancelar(cliente, evento, auth(ASISTENTE)).status_code == 204
    despues_de_cancelar = cliente.get(f"/events/{evento.id}").json()

    assert despues_de_inscribirse["available_spots"] == 4
    assert despues_de_cancelar["available_spots"] == 5


# --- Reglas del evento que dependen de las inscripciones -----------------------------------


def editar_evento(cliente, evento: Event, cuerpo: dict, headers: dict):
    return cliente.patch(f"/events/{evento.id}", json=cuerpo, headers=headers)


def test_bajar_la_capacidad_por_debajo_de_las_activas_responde_409_y_no_la_cambia(
    cliente, repos, auth
):
    evento = repos.evento(capacity=5)
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento)
    repos.inscribir(ADMIN, evento, EstadoInscripcion.CANCELLED)

    respuesta = editar_evento(cliente, evento, {"capacity": 1}, auth(ORGANIZADOR))

    assert_conflicto(respuesta, "capacity-below-registrations")
    assert "2" in respuesta.json()["detail"]
    assert evento.capacity == 5
    assert repos.eventos.bloqueos == [evento.id]


def test_igualar_la_capacidad_a_las_activas_se_acepta(cliente, repos, auth):
    evento = repos.evento(capacity=5)
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento)
    repos.inscribir(ADMIN, evento, EstadoInscripcion.CANCELLED)

    respuesta = editar_evento(cliente, evento, {"capacity": 2}, auth(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert evento.capacity == 2


def test_despublicar_con_inscripciones_activas_responde_409_has_registrations(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento)

    respuesta = cliente.post(f"/events/{evento.id}/unpublish", headers=auth(ORGANIZADOR))

    assert_conflicto(respuesta, "has-registrations")
    assert evento.status == EstadoEvento.PUBLISHED
    assert repos.eventos.bloqueos == [evento.id]


def test_despublicar_con_solo_inscripciones_canceladas_se_acepta(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento, EstadoInscripcion.CANCELLED)

    respuesta = cliente.post(f"/events/{evento.id}/unpublish", headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert evento.status == EstadoEvento.DRAFT


def test_eliminar_con_inscripciones_activas_responde_409_y_sugiere_cancelar(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento)

    respuesta = cliente.delete(f"/events/{evento.id}", headers=auth(ADMIN))

    assert_conflicto(respuesta, "has-registrations")
    assert respuesta.json()["detail"] == "Cancelá el evento en lugar de eliminarlo"
    assert evento.id in repos.eventos.eventos
    assert repos.eventos.bloqueos == [evento.id]


def test_eliminar_con_solo_inscripciones_canceladas_se_acepta(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento, EstadoInscripcion.CANCELLED)

    respuesta = cliente.delete(f"/events/{evento.id}", headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 204, respuesta.text
    assert evento.id not in repos.eventos.eventos


# --- Toda respuesta con un evento trae su conteo real ---------------------------------------


def test_el_listado_cuenta_los_inscritos_de_toda_la_pagina_en_una_sola_llamada(cliente, repos):
    eventos = [repos.evento(capacity=5) for _ in range(3)]
    repos.inscribir(ASISTENTE, eventos[0])
    repos.inscribir(OTRO_ASISTENTE, eventos[0])
    repos.inscribir(ASISTENTE, eventos[2])
    repos.inscribir(OTRO_ASISTENTE, eventos[2], EstadoInscripcion.CANCELLED)

    respuesta = cliente.get("/events")

    assert respuesta.status_code == 200, respuesta.text
    por_id = {
        e["id"]: (e["registered_count"], e["available_spots"]) for e in respuesta.json()["items"]
    }
    assert por_id == {
        str(eventos[0].id): (2, 3),
        str(eventos[1].id): (0, 5),
        str(eventos[2].id): (1, 4),
    }
    assert [sorted(ids) for ids in repos.eventos.conteos] == [sorted(e.id for e in eventos)]


def test_editar_responde_con_el_conteo_real(cliente, repos, auth):
    evento = repos.evento(capacity=5)
    repos.inscribir(ASISTENTE, evento)

    respuesta = editar_evento(cliente, evento, {"name": "PyCon Medellín"}, auth(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert (respuesta.json()["registered_count"], respuesta.json()["available_spots"]) == (1, 4)


@pytest.mark.parametrize(
    ("estado", "accion"),
    [(EstadoEvento.DRAFT, "publish"), (EstadoEvento.PUBLISHED, "cancel")],
    ids=["publicar", "cancelar"],
)
def test_cambiar_el_estado_responde_con_el_conteo_real(cliente, repos, auth, estado, accion):
    evento = repos.evento(estado, capacity=5)
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento)

    respuesta = cliente.post(f"/events/{evento.id}/{accion}", headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert (respuesta.json()["registered_count"], respuesta.json()["available_spots"]) == (2, 3)


# --- is_registered en el detalle -------------------------------------------------------------


def test_el_detalle_dice_si_el_usuario_esta_inscrito(cliente, repos, auth):
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento, EstadoInscripcion.CANCELLED)

    def inscrito(usuario: User | None) -> bool:
        respuesta = cliente.get(f"/events/{evento.id}", headers=auth(usuario))
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json().get("is_registered")

    assert inscrito(ASISTENTE) is True
    assert inscrito(OTRO_ASISTENTE) is False  # su inscripción está cancelada
    assert inscrito(ORGANIZADOR) is False
    assert inscrito(None) is False


def test_estar_inscrito_en_otro_evento_no_cuenta(cliente, repos, auth):
    evento = repos.evento()
    otro = repos.evento()
    repos.inscribir(ASISTENTE, otro)

    respuesta = cliente.get(f"/events/{evento.id}", headers=auth(ASISTENTE))

    assert respuesta.json().get("is_registered") is False


# --- Mis inscripciones ----------------------------------------------------------------------


def mis_inscripciones(cliente, headers: dict, **params):
    return cliente.get("/me/registrations", headers=headers, params=params)


def test_mis_inscripciones_sin_token_responde_401(cliente, repos):
    assert mis_inscripciones(cliente, {}).status_code == 401


def test_mis_inscripciones_trae_solo_las_del_usuario_con_el_resumen_del_evento(
    cliente, repos, auth
):
    evento = repos.evento(location="Ágora Bogotá")
    propia = repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento)

    respuesta = mis_inscripciones(cliente, auth(ASISTENTE))

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["total"], cuerpo["page"], cuerpo["page_size"]) == (1, 1, 12)
    [item] = cuerpo["items"]
    assert item["id"] == str(propia.id)
    assert item["event_id"] == str(evento.id)
    assert item["status"] == "ACTIVE"
    assert item["created_at"].endswith("Z")
    assert item["cancelled_at"] is None
    assert item["event"] == {
        "id": str(evento.id),
        "name": "PyCon Bogotá",
        "start_at": evento.start_at.isoformat().replace("+00:00", "Z"),
        "location": "Ágora Bogotá",
        "status": "PUBLISHED",
        "is_finished": False,
    }
    [consulta] = repos.inscripciones.consultas_del_usuario
    assert consulta["id_usuario"] == ASISTENTE.id


def test_mis_inscripciones_por_defecto_pide_las_activas_que_no_terminaron(cliente, repos, auth):
    mis_inscripciones(cliente, auth(ASISTENTE))

    pedidos = [(c["estado"], c["cuando"]) for c in repos.inscripciones.consultas_del_usuario]
    assert pedidos == [(EstadoInscripcion.ACTIVE, "upcoming")]


def test_mis_inscripciones_filtra_por_estado_y_por_cuando(cliente, repos, auth):
    pasado = repos.evento()
    pasado.start_at -= timedelta(days=60)
    pasado.end_at -= timedelta(days=60)
    cancelada = repos.inscribir(ASISTENTE, pasado, EstadoInscripcion.CANCELLED)
    repos.inscribir(ASISTENTE, repos.evento(), EstadoInscripcion.CANCELLED)

    respuesta = mis_inscripciones(cliente, auth(ASISTENTE), status="CANCELLED", when="past")

    assert respuesta.status_code == 200, respuesta.text
    [consulta] = repos.inscripciones.consultas_del_usuario
    assert (consulta["estado"], consulta["cuando"]) == (EstadoInscripcion.CANCELLED, "past")
    [item] = respuesta.json()["items"]
    assert item["id"] == str(cancelada.id)
    assert item["event"]["is_finished"] is True


@pytest.mark.parametrize(
    "params", [{"status": "PENDING"}, {"when": "ayer"}], ids=["status", "when"]
)
def test_mis_inscripciones_con_un_filtro_invalido_responde_422(cliente, repos, auth, params):
    respuesta = mis_inscripciones(cliente, auth(ASISTENTE), **params)

    assert respuesta.status_code == 422
    assert repos.inscripciones.consultas_del_usuario == []


# --- Inscritos y estadísticas del evento ------------------------------------------------------


@pytest.mark.parametrize(
    ("activas", "capacidad", "esperado"),
    [(1, 3, "33.3"), (2, 3, "66.7"), (0, 5, "0.0"), (3, 3, "100.0"), (1, 8, "12.5")],
)
def test_el_porcentaje_de_ocupacion_es_un_decimal_con_un_solo_decimal(activas, capacidad, esperado):
    porcentaje = porcentaje_de_ocupacion(activas, capacidad)

    assert isinstance(porcentaje, Decimal)
    assert str(porcentaje) == esperado


def con_nombre(nombre: str, email: str, repos: Repos) -> User:
    usuario = User(email=email, password_hash="$argon2id$x", role=Rol.ATTENDEE, full_name=nombre)
    repos.usuarios.usuarios[usuario.id] = usuario
    return usuario


def test_las_estadisticas_cuentan_activas_canceladas_cupos_y_ocupacion(cliente, repos, auth):
    evento = repos.evento(capacity=3)
    repos.inscribir(ASISTENTE, evento)
    repos.inscribir(OTRO_ASISTENTE, evento, EstadoInscripcion.CANCELLED)
    repos.inscribir(ADMIN, evento, EstadoInscripcion.CANCELLED)
    repos.inscribir(ASISTENTE, repos.evento())  # de otro evento: no cuenta

    respuesta = cliente.get(f"/events/{evento.id}/stats", headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {
        "active": 1,
        "cancelled": 2,
        "capacity": 3,
        "available_spots": 2,
        "occupancy_pct": 33.3,
    }


def test_la_lista_de_inscritos_trae_nombre_email_estado_y_fecha_de_cada_uno(cliente, repos, auth):
    evento = repos.evento()
    ana = con_nombre("Ana Gómez", "ana@mail.com", repos)
    beto = con_nombre("Beto Ruiz", "beto@mail.com", repos)
    repos.inscribir(ana, evento)
    repos.inscribir(beto, evento, EstadoInscripcion.CANCELLED)
    repos.inscribir(ASISTENTE, repos.evento())  # de otro evento: no aparece

    respuesta = cliente.get(f"/events/{evento.id}/registrations", headers=auth(ADMIN))

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["total"], cuerpo["page"], cuerpo["page_size"]) == (2, 1, 12)
    assert [set(i) for i in cuerpo["items"]] == [{"full_name", "email", "status", "created_at"}] * 2
    assert [(i["full_name"], i["email"], i["status"]) for i in cuerpo["items"]] == [
        ("Ana Gómez", "ana@mail.com", "ACTIVE"),
        ("Beto Ruiz", "beto@mail.com", "CANCELLED"),
    ]
    assert all(i["created_at"].endswith("Z") for i in cuerpo["items"])


GESTION = ["registrations", "stats"]


@pytest.mark.parametrize("recurso", GESTION)
@pytest.mark.parametrize("usuario", [ORGANIZADOR, ADMIN], ids=["dueno", "admin"])
def test_el_dueno_y_el_admin_ven_inscritos_y_estadisticas(cliente, repos, auth, recurso, usuario):
    evento = repos.evento()

    respuesta = cliente.get(f"/events/{evento.id}/{recurso}", headers=auth(usuario))

    assert respuesta.status_code == 200, respuesta.text


@pytest.mark.parametrize("recurso", GESTION)
def test_otro_usuario_recibe_403_en_inscritos_y_estadisticas(cliente, repos, auth, recurso):
    otro_organizador = User(email="o2@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
    repos.usuarios.usuarios[otro_organizador.id] = otro_organizador
    evento = repos.evento()
    repos.inscribir(ASISTENTE, evento)

    for usuario in (ASISTENTE, otro_organizador):
        respuesta = cliente.get(f"/events/{evento.id}/{recurso}", headers=auth(usuario))
        assert respuesta.status_code == 403, (usuario.email, respuesta.text)
        assert respuesta.json()["type"] == "forbidden"


@pytest.mark.parametrize("recurso", GESTION)
def test_un_borrador_ajeno_responde_404_en_inscritos_y_estadisticas(cliente, repos, auth, recurso):
    borrador = repos.evento(EstadoEvento.DRAFT)

    respuesta = cliente.get(f"/events/{borrador.id}/{recurso}", headers=auth(ASISTENTE))

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "not-found"


@pytest.mark.parametrize("recurso", GESTION)
def test_sin_token_inscritos_y_estadisticas_responden_401(cliente, repos, recurso):
    evento = repos.evento()

    assert cliente.get(f"/events/{evento.id}/{recurso}").status_code == 401
