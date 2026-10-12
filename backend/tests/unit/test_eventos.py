from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.api.dependencias import repositorio_eventos, repositorio_usuarios
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.evento import EstadoEvento, Event
from app.models.sesion import Session as Sesion
from app.models.usuario import User
from app.services import eventos as servicio_eventos
from tests.unit.dobles import RepositorioEventosFalso, RepositorioUsuariosFalso

ASISTENTE = User(email="asistente@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
ORGANIZADOR = User(email="orga@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
OTRO_ORGANIZADOR = User(email="otro@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
ADMIN = User(email="admin@mail.com", password_hash="$argon2id$x", role=Rol.ADMIN)


@pytest.fixture
def eventos(app) -> RepositorioEventosFalso:
    repo = RepositorioEventosFalso()
    usuarios = RepositorioUsuariosFalso(ASISTENTE, ORGANIZADOR, OTRO_ORGANIZADOR, ADMIN)
    app.dependency_overrides[repositorio_usuarios] = lambda: usuarios
    app.dependency_overrides[repositorio_eventos] = lambda: repo
    return repo


@pytest.fixture
def token(settings):
    def de(usuario: User) -> str:
        return crear_access_token(usuario.id, settings.jwt_secret, 5)

    return de


def cuerpo_valido(**cambios) -> dict:
    inicio = datetime.now(UTC) + timedelta(days=30)
    datos = {
        "name": "PyCon Bogotá",
        "description": "Charlas de Python",
        "location": "Bogotá",
        "start_at": inicio.isoformat(),
        "end_at": (inicio + timedelta(hours=8)).isoformat(),
        "capacity": 100,
    }
    return datos | cambios


def crear(cliente, cuerpo: dict, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.post("/events", json=cuerpo, headers=headers)


# --- Crear: permisos -----------------------------------------------------------------------


def test_un_asistente_no_puede_crear_un_evento(cliente, eventos, token):
    respuesta = crear(cliente, cuerpo_valido(), token(ASISTENTE))

    assert respuesta.status_code == 403
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert eventos.eventos == {}


def test_sin_token_no_se_puede_crear_un_evento(cliente, eventos):
    respuesta = crear(cliente, cuerpo_valido())

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
    assert eventos.eventos == {}


@pytest.mark.parametrize("usuario", [ORGANIZADOR, ADMIN], ids=["organizador", "admin"])
def test_quien_tiene_el_permiso_crea_un_borrador_a_su_nombre(cliente, eventos, token, usuario):
    respuesta = crear(cliente, cuerpo_valido(capacity=40), token(usuario))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "DRAFT"
    assert cuerpo["organizer_id"] == str(usuario.id)
    assert cuerpo["name"] == "PyCon Bogotá"
    assert cuerpo["registered_count"] == 0
    assert cuerpo["available_spots"] == 40
    assert cuerpo["is_finished"] is False
    assert cuerpo["start_at"].endswith("Z")
    assert len(eventos.eventos) == 1


# --- Crear: validaciones -------------------------------------------------------------------

AHORA = datetime.now(UTC)
INICIO = AHORA + timedelta(days=30)


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"end_at": INICIO.isoformat()}, "end_at"),
        ({"end_at": (INICIO - timedelta(minutes=1)).isoformat()}, "end_at"),
        ({"start_at": (AHORA - timedelta(hours=1)).isoformat()}, "start_at"),
        ({"start_at": "2030-01-10T15:00:00", "end_at": "2030-01-10T18:00:00Z"}, "start_at"),
        ({"capacity": 0}, "capacity"),
        ({"capacity": 100_001}, "capacity"),
        ({"name": "ab"}, "name"),
        ({"name": "  ab  "}, "name"),
        ({"name": "a" * 151}, "name"),
        ({"description": "a" * 5001}, "description"),
        ({"location": "a" * 201}, "location"),
        ({"status": "PUBLISHED"}, "status"),
        ({"organizer_id": str(ADMIN.id)}, "organizer_id"),
        ({"name": "abc\x00"}, "name"),
        ({"description": "texto\x00"}, "description"),
        ({"location": "\x00lugar"}, "location"),
    ],
    ids=[
        "fin-igual-inicio",
        "fin-antes-inicio",
        "inicio-pasado",
        "inicio-sin-zona",
        "capacidad-0",
        "capacidad-100001",
        "nombre-2",
        "nombre-2-con-espacios",
        "nombre-151",
        "descripcion-5001",
        "lugar-201",
        "con-status",
        "con-organizer_id",
        "nombre-con-nul",
        "descripcion-con-nul",
        "lugar-con-nul",
    ],
)
def test_un_cuerpo_invalido_responde_422_en_su_campo(cliente, eventos, token, cambios, campo):
    cuerpo = cuerpo_valido(
        start_at=INICIO.isoformat(), end_at=(INICIO + timedelta(hours=8)).isoformat()
    )

    respuesta = crear(cliente, cuerpo | cambios, token(ORGANIZADOR))

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert [e["field"] for e in respuesta.json()["errors"]] == [campo]
    assert eventos.eventos == {}


def test_un_texto_con_el_caracter_nulo_se_rechaza_con_el_mensaje_en_espanol(
    cliente, eventos, token
):
    respuesta = crear(cliente, cuerpo_valido(name="PyCon\x00"), token(ORGANIZADOR))

    assert respuesta.status_code == 422
    assert respuesta.json()["errors"] == [
        {"field": "name", "message": "No puede contener el carácter nulo"}
    ]


def test_el_nombre_se_guarda_sin_espacios_al_inicio_ni_al_final(cliente, eventos, token):
    respuesta = crear(cliente, cuerpo_valido(name="  PyCon  "), token(ORGANIZADOR))

    assert respuesta.status_code == 201
    assert respuesta.json()["name"] == "PyCon"


# --- Ver: visibilidad ----------------------------------------------------------------------


def evento(estado: EstadoEvento, organizador: User = ORGANIZADOR) -> Event:
    inicio = datetime.now(UTC) + timedelta(days=30)
    nuevo = Event(
        name="PyCon Bogotá",
        start_at=inicio,
        end_at=inicio + timedelta(hours=8),
        capacity=100,
        status=estado,
        organizer_id=organizador.id,
    )
    nuevo.created_at = nuevo.updated_at = datetime.now(UTC)
    return nuevo


PUBLICADO, CANCELADO, BORRADOR = (
    EstadoEvento.PUBLISHED,
    EstadoEvento.CANCELLED,
    EstadoEvento.DRAFT,
)

# (quién consulta, estado, dueño del evento, ¿lo ve?): una fila por caso de la tabla de visibilidad.
VISIBILIDAD = {
    "anonimo-publicado": (None, PUBLICADO, ORGANIZADOR, True),
    "anonimo-cancelado": (None, CANCELADO, ORGANIZADOR, True),
    "anonimo-borrador": (None, BORRADOR, ORGANIZADOR, False),
    "asistente-publicado": (ASISTENTE, PUBLICADO, ORGANIZADOR, True),
    "asistente-cancelado": (ASISTENTE, CANCELADO, ORGANIZADOR, True),
    "asistente-borrador": (ASISTENTE, BORRADOR, ORGANIZADOR, False),
    # Un asistente que fue organizador: sus borradores viejos tampoco los ve.
    "asistente-borrador-propio": (ASISTENTE, BORRADOR, ASISTENTE, False),
    "organizador-publicado-ajeno": (OTRO_ORGANIZADOR, PUBLICADO, ORGANIZADOR, True),
    "organizador-cancelado-ajeno": (OTRO_ORGANIZADOR, CANCELADO, ORGANIZADOR, True),
    "organizador-borrador-propio": (ORGANIZADOR, BORRADOR, ORGANIZADOR, True),
    "organizador-borrador-ajeno": (OTRO_ORGANIZADOR, BORRADOR, ORGANIZADOR, False),
    "admin-publicado": (ADMIN, PUBLICADO, ORGANIZADOR, True),
    "admin-cancelado": (ADMIN, CANCELADO, ORGANIZADOR, True),
    "admin-borrador-ajeno": (ADMIN, BORRADOR, ORGANIZADOR, True),
}


@pytest.mark.parametrize("caso", VISIBILIDAD)
def test_quien_ve_cada_evento(caso):
    usuario, estado, dueno, lo_ve = VISIBILIDAD[caso]

    assert servicio_eventos.puede_ver(usuario, evento(estado, dueno)) is lo_ve


def ver(cliente, id_evento, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.get(f"/events/{id_evento}", headers=headers)


def test_un_anonimo_ve_un_evento_publicado(cliente, eventos):
    publicado = eventos.crear(evento(PUBLICADO))

    respuesta = ver(cliente, publicado.id)

    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == str(publicado.id)
    assert respuesta.json()["status"] == "PUBLISHED"


def test_un_borrador_que_no_puede_ver_responde_404_y_no_403(cliente, eventos, token):
    borrador = eventos.crear(evento(BORRADOR))

    for respuesta in (ver(cliente, borrador.id), ver(cliente, borrador.id, token(ASISTENTE))):
        assert respuesta.status_code == 404
        assert respuesta.headers["content-type"] == "application/problem+json"
    assert ver(cliente, borrador.id, token(ORGANIZADOR)).status_code == 200


def test_un_evento_que_no_existe_responde_404(cliente, eventos):
    assert ver(cliente, uuid4()).status_code == 404


def test_un_token_invalido_en_el_detalle_se_trata_como_anonimo(cliente, eventos, settings):
    publicado = eventos.crear(evento(PUBLICADO))
    borrador = eventos.crear(evento(BORRADOR))
    vencido = crear_access_token(ORGANIZADOR.id, settings.jwt_secret, -1)

    assert ver(cliente, publicado.id, "esto.no.es-un-jwt").status_code == 200
    assert ver(cliente, borrador.id, vencido).status_code == 404


# --- Transiciones --------------------------------------------------------------------------


def accion(cliente, id_evento, nombre: str, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.post(f"/events/{id_evento}/{nombre}", headers=headers)


@pytest.mark.parametrize(
    ("estado", "nombre", "queda"),
    [
        (BORRADOR, "publish", "PUBLISHED"),
        (PUBLICADO, "unpublish", "DRAFT"),
        (BORRADOR, "cancel", "CANCELLED"),
        (PUBLICADO, "cancel", "CANCELLED"),
    ],
    ids=["publicar", "despublicar", "cancelar-borrador", "cancelar-publicado"],
)
def test_el_dueno_cambia_el_estado_con_una_transicion_valida(
    cliente, eventos, token, estado, nombre, queda
):
    existente = eventos.crear(evento(estado))

    respuesta = accion(cliente, existente.id, nombre, token(ORGANIZADOR))

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == queda
    assert eventos.eventos[existente.id].status == queda


@pytest.mark.parametrize(
    ("estado", "nombre"),
    [
        (CANCELADO, "publish"),
        (CANCELADO, "cancel"),
        (BORRADOR, "unpublish"),
        (PUBLICADO, "publish"),
        (CANCELADO, "unpublish"),
    ],
    ids=[
        "publicar-cancelado",
        "cancelar-cancelado",
        "despublicar-borrador",
        "publicar-publicado",
        "despublicar-cancelado",
    ],
)
def test_una_transicion_que_no_existe_responde_409_invalid_transition(
    cliente, eventos, token, estado, nombre
):
    existente = eventos.crear(evento(estado))

    respuesta = accion(cliente, existente.id, nombre, token(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.json()["type"] == "invalid-transition"
    assert eventos.eventos[existente.id].status == estado


def en_el_pasado(nuevo: Event, *, termino: bool) -> Event:
    """Corre el evento: empezó hace una hora y, si `termino`, ya terminó."""
    nuevo.start_at = datetime.now(UTC) - timedelta(hours=2)
    nuevo.end_at = nuevo.start_at + timedelta(hours=1 if termino else 8)
    return nuevo


def test_no_se_publica_un_evento_que_ya_empezo(cliente, eventos, token):
    empezado = eventos.crear(en_el_pasado(evento(BORRADOR), termino=False))

    respuesta = accion(cliente, empezado.id, "publish", token(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "invalid-transition"
    assert eventos.eventos[empezado.id].status == BORRADOR


def test_no_se_cancela_un_evento_finalizado(cliente, eventos, token):
    finalizado = eventos.crear(en_el_pasado(evento(PUBLICADO), termino=True))

    respuesta = accion(cliente, finalizado.id, "cancel", token(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "invalid-transition"
    assert eventos.eventos[finalizado.id].status == PUBLICADO


@pytest.mark.parametrize("nombre", ["publish", "unpublish", "cancel"])
def test_sin_token_no_se_cambia_el_estado(cliente, eventos, nombre):
    existente = eventos.crear(evento(PUBLICADO))

    respuesta = accion(cliente, existente.id, nombre)

    assert respuesta.status_code == 401
    assert eventos.eventos[existente.id].status == PUBLICADO


# --- Editar --------------------------------------------------------------------------------


def editar(cliente, id_evento, cuerpo: dict, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.patch(f"/events/{id_evento}", json=cuerpo, headers=headers)


def test_el_dueno_edita_solo_lo_que_manda(cliente, eventos, token):
    existente = eventos.crear(evento(PUBLICADO))
    inicio_guardado = existente.start_at

    respuesta = editar(
        cliente, existente.id, {"name": "  PyCon 2030 ", "capacity": 80}, token(ORGANIZADOR)
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["name"] == "PyCon 2030"
    assert cuerpo["capacity"] == 80
    assert cuerpo["available_spots"] == 80
    assert cuerpo["status"] == "PUBLISHED"
    guardado = eventos.eventos[existente.id]
    assert (guardado.name, guardado.capacity) == ("PyCon 2030", 80)
    assert guardado.start_at == inicio_guardado


def test_se_puede_mover_el_evento_a_otras_fechas_futuras(cliente, eventos, token):
    existente = eventos.crear(evento(BORRADOR))
    inicio = datetime.now(UTC) + timedelta(days=60)
    cambios = {
        "start_at": inicio.isoformat(),
        "end_at": (inicio + timedelta(hours=2)).isoformat(),
    }

    respuesta = editar(cliente, existente.id, cambios, token(ORGANIZADOR))

    assert respuesta.status_code == 200
    assert eventos.eventos[existente.id].start_at == inicio


@pytest.mark.parametrize("estado", [CANCELADO, PUBLICADO], ids=["cancelado", "finalizado"])
def test_un_evento_cancelado_o_finalizado_no_se_edita(cliente, eventos, token, estado):
    existente = evento(estado)
    if estado == PUBLICADO:
        en_el_pasado(existente, termino=True)
    eventos.crear(existente)

    respuesta = editar(cliente, existente.id, {"name": "Otro nombre"}, token(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert eventos.eventos[existente.id].name == "PyCon Bogotá"


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"status": "PUBLISHED"}, "status"),
        ({"organizer_id": str(ADMIN.id)}, "organizer_id"),
        ({"name": "ab"}, "name"),
        ({"name": None}, "name"),
        ({"capacity": 0}, "capacity"),
        ({"capacity": None}, "capacity"),
        ({"location": "a" * 201}, "location"),
        ({"start_at": "2030-01-10T15:00:00"}, "start_at"),
        ({"end_at": None}, "end_at"),
        # El fin se compara con el inicio guardado aunque el inicio no venga en el cuerpo.
        ({"end_at": (INICIO - timedelta(days=1)).isoformat()}, "end_at"),
        # Y un inicio nuevo, con el fin guardado.
        ({"start_at": (INICIO + timedelta(days=1)).isoformat()}, "end_at"),
        ({"start_at": (AHORA - timedelta(hours=1)).isoformat()}, "start_at"),
        ({"name": "abc\x00"}, "name"),
        ({"description": "texto\x00"}, "description"),
        ({"location": "\x00lugar"}, "location"),
    ],
    ids=[
        "con-status",
        "con-organizer_id",
        "nombre-2",
        "nombre-nulo",
        "capacidad-0",
        "capacidad-nula",
        "lugar-201",
        "inicio-sin-zona",
        "fin-nulo",
        "fin-antes-del-inicio-guardado",
        "inicio-despues-del-fin-guardado",
        "inicio-pasado",
        "nombre-con-nul",
        "descripcion-con-nul",
        "lugar-con-nul",
    ],
)
def test_una_edicion_invalida_responde_422_en_su_campo(cliente, eventos, token, cambios, campo):
    existente = evento(PUBLICADO)
    existente.start_at, existente.end_at = INICIO, INICIO + timedelta(hours=8)
    eventos.crear(existente)

    respuesta = editar(cliente, existente.id, cambios, token(ORGANIZADOR))

    assert respuesta.status_code == 422
    assert [e["field"] for e in respuesta.json()["errors"]] == [campo]
    guardado = eventos.eventos[existente.id]
    assert (guardado.name, guardado.start_at, guardado.end_at, guardado.capacity) == (
        "PyCon Bogotá",
        INICIO,
        INICIO + timedelta(hours=8),
        100,
    )


def con_sesion(eventos: RepositorioEventosFalso, evento: Event, desde: int, hasta: int) -> None:
    """Una sesión entre las horas `desde` y `hasta` contadas desde el inicio del evento."""
    sesion = Sesion(
        event_id=evento.id,
        title="Testing en Python",
        start_at=evento.start_at + timedelta(hours=desde),
        end_at=evento.start_at + timedelta(hours=hasta),
    )
    eventos.sesiones[sesion.id] = sesion


def test_achicar_las_fechas_dejando_sesiones_afuera_responde_409(cliente, eventos, token):
    existente = evento(PUBLICADO)
    existente.start_at, existente.end_at = INICIO, INICIO + timedelta(hours=8)
    eventos.crear(existente)
    con_sesion(eventos, existente, 0, 1)  # queda afuera: empieza antes del nuevo inicio
    con_sesion(eventos, existente, 2, 3)
    con_sesion(eventos, existente, 6, 8)  # queda afuera: termina después del nuevo fin
    cambios = {
        "start_at": (INICIO + timedelta(hours=1)).isoformat(),
        "end_at": (INICIO + timedelta(hours=5)).isoformat(),
    }

    respuesta = editar(cliente, existente.id, cambios, token(ORGANIZADOR))

    assert respuesta.status_code == 409
    problema = respuesta.json()
    assert problema["type"] == "sessions-outside-range"
    assert problema["detail"] == "2 sesiones quedan fuera de las fechas nuevas"
    guardado = eventos.eventos[existente.id]
    assert (guardado.start_at, guardado.end_at) == (INICIO, INICIO + timedelta(hours=8))


def test_achicar_las_fechas_dejando_una_sola_sesion_afuera_lo_dice_en_singular(
    cliente, eventos, token
):
    existente = evento(PUBLICADO)
    existente.start_at, existente.end_at = INICIO, INICIO + timedelta(hours=8)
    eventos.crear(existente)
    con_sesion(eventos, existente, 6, 8)

    respuesta = editar(
        cliente,
        existente.id,
        {"end_at": (INICIO + timedelta(hours=7)).isoformat()},
        token(ORGANIZADOR),
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "1 sesión queda fuera de las fechas nuevas"


def test_cambiar_las_fechas_sin_dejar_sesiones_afuera_se_acepta(cliente, eventos, token):
    existente = evento(PUBLICADO)
    existente.start_at, existente.end_at = INICIO, INICIO + timedelta(hours=8)
    eventos.crear(existente)
    con_sesion(eventos, existente, 1, 2)
    con_sesion(eventos, existente, 3, 4)
    # Justo en los bordes de las sesiones: la primera empieza al inicio, la última termina al fin.
    cambios = {
        "start_at": (INICIO + timedelta(hours=1)).isoformat(),
        "end_at": (INICIO + timedelta(hours=4)).isoformat(),
    }

    respuesta = editar(cliente, existente.id, cambios, token(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert eventos.eventos[existente.id].end_at == INICIO + timedelta(hours=4)


def test_sin_token_no_se_edita(cliente, eventos):
    existente = eventos.crear(evento(PUBLICADO))

    assert editar(cliente, existente.id, {"name": "Otro nombre"}).status_code == 401
    assert eventos.eventos[existente.id].name == "PyCon Bogotá"


# --- Eliminar ------------------------------------------------------------------------------


def eliminar(cliente, id_evento, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.delete(f"/events/{id_evento}", headers=headers)


def test_el_dueno_elimina_su_evento(cliente, eventos, token):
    existente = eventos.crear(evento(PUBLICADO))

    respuesta = eliminar(cliente, existente.id, token(ORGANIZADOR))

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert eventos.eventos == {}


def test_sin_token_no_se_elimina(cliente, eventos):
    existente = eventos.crear(evento(PUBLICADO))

    assert eliminar(cliente, existente.id).status_code == 401
    assert existente.id in eventos.eventos


def test_eliminar_un_evento_que_no_existe_responde_404(cliente, eventos, token):
    assert eliminar(cliente, uuid4(), token(ORGANIZADOR)).status_code == 404


# --- Permisos de escritura -----------------------------------------------------------------

# Cada acción de escritura, con lo que hay que mandar para que sea válida sobre un publicado.
ESCRITURAS = {
    "editar": lambda c, id_, t: editar(c, id_, {"name": "Otro nombre"}, t),
    "despublicar": lambda c, id_, t: accion(c, id_, "unpublish", t),
    "cancelar": lambda c, id_, t: accion(c, id_, "cancel", t),
    "eliminar": lambda c, id_, t: eliminar(c, id_, t),
}


def sin_cambios(eventos: RepositorioEventosFalso, original: Event) -> bool:
    guardado = eventos.eventos.get(original.id)
    return guardado is not None and (guardado.name, guardado.status) == (
        "PyCon Bogotá",
        original.status,
    )


@pytest.mark.parametrize("escritura", ESCRITURAS)
@pytest.mark.parametrize(
    ("usuario", "dueno"),
    [(ASISTENTE, ORGANIZADOR), (OTRO_ORGANIZADOR, ORGANIZADOR), (ASISTENTE, ASISTENTE)],
    ids=["asistente", "organizador-ajeno", "asistente-que-fue-organizador"],
)
def test_sin_el_permiso_o_sin_ser_el_dueno_un_publicado_responde_403(
    cliente, eventos, token, escritura, usuario, dueno
):
    publicado = eventos.crear(evento(PUBLICADO, dueno))

    respuesta = ESCRITURAS[escritura](cliente, publicado.id, token(usuario))

    assert respuesta.status_code == 403
    assert respuesta.json()["type"] == "forbidden"
    assert sin_cambios(eventos, publicado)


@pytest.mark.parametrize("usuario", [ASISTENTE, OTRO_ORGANIZADOR], ids=["asistente", "otro-orga"])
@pytest.mark.parametrize(
    "escritura",
    {
        "editar": ESCRITURAS["editar"],
        "publicar": lambda c, id_, t: accion(c, id_, "publish", t),
        "cancelar": ESCRITURAS["cancelar"],
        "eliminar": ESCRITURAS["eliminar"],
    }.items(),
    ids=lambda par: par[0],
)
def test_un_borrador_ajeno_responde_404_y_no_403(cliente, eventos, token, escritura, usuario):
    borrador = eventos.crear(evento(BORRADOR, ORGANIZADOR))
    _, hacer = escritura

    respuesta = hacer(cliente, borrador.id, token(usuario))

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "not-found"
    assert sin_cambios(eventos, borrador)


def test_el_admin_edita_publica_y_elimina_eventos_ajenos(cliente, eventos, token):
    publicado = eventos.crear(evento(PUBLICADO))
    borrador = eventos.crear(evento(BORRADOR))

    editado = editar(cliente, publicado.id, {"name": "Otro nombre"}, token(ADMIN))
    publicado_por_admin = accion(cliente, borrador.id, "publish", token(ADMIN))
    eliminado = eliminar(cliente, publicado.id, token(ADMIN))

    assert editado.status_code == 200
    assert editado.json()["name"] == "Otro nombre"
    assert editado.json()["organizer_id"] == str(ORGANIZADOR.id)
    assert publicado_por_admin.status_code == 200
    assert eliminado.status_code == 204
    assert list(eventos.eventos) == [borrador.id]
