"""Sesiones de un evento: alta, listado, edición y baja, con sus permisos y validaciones, y las
reglas de horario: dentro del evento, sin cruces de ponente ni de sala, y nada de cambios en un
evento cancelado o finalizado."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.api.dependencias import (
    repositorio_eventos,
    repositorio_ponentes,
    repositorio_sesiones,
    repositorio_usuarios,
)
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.evento import EstadoEvento, Event
from app.models.ponente import Speaker
from app.models.sesion import Session as Sesion
from app.models.usuario import User
from tests.unit.dobles import (
    RepositorioEventosFalso,
    RepositorioPonentesFalso,
    RepositorioSesionesFalso,
    RepositorioUsuariosFalso,
)

ASISTENTE = User(email="asistente@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
ORGANIZADOR = User(email="orga@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
OTRO_ORGANIZADOR = User(email="otro@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
ADMIN = User(email="admin@mail.com", password_hash="$argon2id$x", role=Rol.ADMIN)

# 13:00 UTC son las 8:00 en Bogotá. El evento dura de 8:00 a 18:00 (hora de Bogotá).
DIA = datetime(2030, 1, 10, tzinfo=UTC)
INICIO_EVENTO = DIA + timedelta(hours=13)
FIN_EVENTO = DIA + timedelta(hours=23)


def hora(h: int, m: int = 0) -> datetime:
    """Una hora del día del evento, en hora de Bogotá (UTC-5)."""
    return DIA + timedelta(hours=h + 5, minutes=m)


class Repos:
    def __init__(self) -> None:
        self.eventos = RepositorioEventosFalso()
        self.ponentes = RepositorioPonentesFalso()
        self.sesiones = RepositorioSesionesFalso(self.eventos, self.ponentes)
        # Un solo registro de bloqueos, para ver el orden entre tablas.
        self.ponentes.bloqueos = self.eventos.bloqueos

    def evento(
        self, estado: EstadoEvento = EstadoEvento.PUBLISHED, dueno: User = ORGANIZADOR, **cambios
    ) -> Event:
        datos = {
            "name": "PyCon Bogotá",
            "start_at": INICIO_EVENTO,
            "end_at": FIN_EVENTO,
            "capacity": 100,
            "status": estado,
            "organizer_id": dueno.id,
        } | cambios
        return self.eventos.crear(Event(**datos))

    def ponente(self, nombre: str = "Ana Pérez") -> Speaker:
        return self.ponentes.crear(
            Speaker(full_name=nombre, email=f"{uuid4().hex}@mail.com", created_by=ORGANIZADOR.id)
        )

    def sesion(
        self, evento: Event, inicio: datetime, fin: datetime, *ponentes: Speaker, **cambios
    ) -> Sesion:
        datos = {"title": "Testing en Python", "start_at": inicio, "end_at": fin} | cambios
        return self.sesiones.crear(Sesion(event_id=evento.id, **datos), [p.id for p in ponentes])


@pytest.fixture
def repos(app) -> Repos:
    nuevos = Repos()
    usuarios = RepositorioUsuariosFalso(ASISTENTE, ORGANIZADOR, OTRO_ORGANIZADOR, ADMIN)
    app.dependency_overrides[repositorio_usuarios] = lambda: usuarios
    app.dependency_overrides[repositorio_eventos] = lambda: nuevos.eventos
    app.dependency_overrides[repositorio_ponentes] = lambda: nuevos.ponentes
    app.dependency_overrides[repositorio_sesiones] = lambda: nuevos.sesiones
    return nuevos


@pytest.fixture
def auth(settings):
    def de(usuario: User | None) -> dict:
        if usuario is None:
            return {}
        return {"Authorization": f"Bearer {crear_access_token(usuario.id, settings.jwt_secret, 5)}"}

    return de


def cuerpo(*ponentes: Speaker, **cambios) -> dict:
    datos = {
        "title": "Testing en Python",
        "description": "Pytest de punta a punta",
        "room": "Sala B",
        "start_at": hora(10).isoformat(),
        "end_at": hora(11).isoformat(),
        "capacity": 40,
        "speaker_ids": [str(p.id) for p in ponentes],
    }
    return datos | cambios


def crear(cliente, evento: Event, datos: dict, headers: dict):
    return cliente.post(f"/events/{evento.id}/sessions", json=datos, headers=headers)


def editar(cliente, sesion: Sesion, datos: dict, headers: dict):
    return cliente.patch(f"/sessions/{sesion.id}", json=datos, headers=headers)


def eliminar(cliente, sesion: Sesion, headers: dict):
    return cliente.delete(f"/sessions/{sesion.id}", headers=headers)


# --- Crear y listar ------------------------------------------------------------------------


def test_el_dueno_crea_una_sesion_con_dos_ponentes_y_sin_sus_emails(cliente, repos, auth):
    evento = repos.evento()
    ana, beto = repos.ponente("Ana Pérez"), repos.ponente("Beto Ruiz")

    respuesta = crear(cliente, evento, cuerpo(ana, beto, room="  Sala B "), auth(ORGANIZADOR))

    assert respuesta.status_code == 201, respuesta.text
    creada = respuesta.json()
    assert creada["event_id"] == str(evento.id)
    assert (creada["title"], creada["room"], creada["capacity"]) == (
        "Testing en Python",
        "Sala B",
        40,
    )
    assert creada["start_at"] == "2030-01-10T15:00:00Z"
    assert [p["full_name"] for p in creada["speakers"]] == ["Ana Pérez", "Beto Ruiz"]
    assert all(set(p) == {"id", "full_name", "bio"} for p in creada["speakers"])
    [guardada] = repos.eventos.sesiones.values()
    assert sorted(repos.sesiones.vinculos[guardada.id]) == sorted([ana.id, beto.id])


def test_una_sesion_sin_ponentes_ni_sala_ni_capacidad(cliente, repos, auth):
    evento = repos.evento()

    respuesta = crear(
        cliente, evento, cuerpo(room=None, capacity=None, description=None), auth(ORGANIZADOR)
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["speakers"] == []
    assert (respuesta.json()["room"], respuesta.json()["capacity"]) == (None, None)


def test_listar_ordena_por_inicio_y_no_muestra_el_email_de_los_ponentes(cliente, repos):
    evento = repos.evento()
    otro = repos.evento()
    ana = repos.ponente()
    repos.sesion(evento, hora(14), hora(15), title="Tarde")
    repos.sesion(evento, hora(9), hora(10), ana, title="Mañana")
    repos.sesion(otro, hora(11), hora(12), title="De otro evento")

    respuesta = cliente.get(f"/events/{evento.id}/sessions")

    assert respuesta.status_code == 200
    sesiones = respuesta.json()
    assert [s["title"] for s in sesiones] == ["Mañana", "Tarde"]
    assert sesiones[0]["speakers"] == [{"id": str(ana.id), "full_name": "Ana Pérez", "bio": None}]
    assert "email" not in respuesta.text


@pytest.mark.parametrize(
    "usuario", [None, ASISTENTE, OTRO_ORGANIZADOR], ids=["anonimo", "asistente", "otro-orga"]
)
def test_las_sesiones_de_un_borrador_ajeno_responden_404(cliente, repos, auth, usuario):
    borrador = repos.evento(EstadoEvento.DRAFT)
    repos.sesion(borrador, hora(9), hora(10))

    respuesta = cliente.get(f"/events/{borrador.id}/sessions", headers=auth(usuario))

    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "not-found"


def test_las_sesiones_de_un_borrador_las_ven_su_dueno_y_el_admin(cliente, repos, auth):
    borrador = repos.evento(EstadoEvento.DRAFT)
    repos.sesion(borrador, hora(9), hora(10))

    for usuario in (ORGANIZADOR, ADMIN):
        respuesta = cliente.get(f"/events/{borrador.id}/sessions", headers=auth(usuario))
        assert respuesta.status_code == 200
        assert len(respuesta.json()) == 1


def test_las_sesiones_de_un_evento_que_no_existe_responden_404(cliente, repos):
    assert cliente.get(f"/events/{uuid4()}/sessions").status_code == 404


# --- Validaciones del cuerpo ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"end_at": hora(10).isoformat()}, "end_at"),
        ({"end_at": hora(9).isoformat()}, "end_at"),
        ({"title": "ab"}, "title"),
        ({"title": "  ab  "}, "title"),
        ({"title": "a" * 151}, "title"),
        ({"description": "a" * 2001}, "description"),
        ({"room": "a" * 81}, "room"),
        ({"room": "Sala\x00B"}, "room"),
        ({"capacity": 0}, "capacity"),
        ({"capacity": 101}, "capacity"),
        ({"start_at": "2030-01-10T15:00:00"}, "start_at"),
        ({"event_id": str(uuid4())}, "event_id"),
        ({"speaker_ids": ["no-es-un-uuid"]}, "speaker_ids.0"),
    ],
    ids=[
        "fin-igual-inicio",
        "fin-antes-inicio",
        "titulo-2",
        "titulo-2-con-espacios",
        "titulo-151",
        "descripcion-2001",
        "sala-81",
        "sala-con-nulo",
        "capacidad-0",
        "capacidad-mayor-que-la-del-evento",
        "inicio-sin-zona",
        "con-event_id",
        "ponente-no-uuid",
    ],
)
def test_una_sesion_invalida_responde_422_en_su_campo(cliente, repos, auth, cambios, campo):
    evento = repos.evento(capacity=100)

    respuesta = crear(cliente, evento, cuerpo(**cambios), auth(ORGANIZADOR))

    assert respuesta.status_code == 422
    assert [e["field"] for e in respuesta.json()["errors"]] == [campo]
    assert repos.eventos.sesiones == {}


def test_un_ponente_que_no_existe_responde_422(cliente, repos, auth):
    evento = repos.evento()
    ana = repos.ponente()
    datos = cuerpo(ana) | {"speaker_ids": [str(ana.id), str(uuid4())]}

    respuesta = crear(cliente, evento, datos, auth(ORGANIZADOR))

    assert respuesta.status_code == 422
    assert [e["field"] for e in respuesta.json()["errors"]] == ["speaker_ids"]
    assert repos.eventos.sesiones == {}


def test_la_capacidad_igual_a_la_del_evento_se_acepta(cliente, repos, auth):
    evento = repos.evento(capacity=100)

    respuesta = crear(cliente, evento, cuerpo(capacity=100), auth(ORGANIZADOR))

    assert respuesta.status_code == 201


# --- Permisos de escritura -----------------------------------------------------------------


def test_sin_token_no_se_crea_ni_edita_ni_elimina(cliente, repos):
    evento = repos.evento()
    sesion = repos.sesion(evento, hora(9), hora(10))

    respuestas = [
        crear(cliente, evento, cuerpo(), {}),
        editar(cliente, sesion, {"title": "Otro título"}, {}),
        eliminar(cliente, sesion, {}),
    ]

    assert [r.status_code for r in respuestas] == [401, 401, 401]
    assert respuestas[0].headers["www-authenticate"] == "Bearer"
    assert list(repos.eventos.sesiones.values()) == [sesion]
    assert sesion.title == "Testing en Python"


@pytest.mark.parametrize("usuario", [ASISTENTE, OTRO_ORGANIZADOR], ids=["asistente", "otro-orga"])
def test_en_un_evento_ajeno_visible_se_responde_403(cliente, repos, auth, usuario):
    evento = repos.evento(EstadoEvento.PUBLISHED, ORGANIZADOR)
    sesion = repos.sesion(evento, hora(9), hora(10))

    respuestas = [
        crear(cliente, evento, cuerpo(), auth(usuario)),
        editar(cliente, sesion, {"title": "Otro título"}, auth(usuario)),
        eliminar(cliente, sesion, auth(usuario)),
    ]

    assert [r.status_code for r in respuestas] == [403, 403, 403]
    assert {r.json()["type"] for r in respuestas} == {"forbidden"}
    assert list(repos.eventos.sesiones.values()) == [sesion]
    assert sesion.title == "Testing en Python"


def test_en_un_borrador_ajeno_se_responde_404(cliente, repos, auth):
    borrador = repos.evento(EstadoEvento.DRAFT, ORGANIZADOR)
    sesion = repos.sesion(borrador, hora(9), hora(10))
    otro = auth(OTRO_ORGANIZADOR)

    respuestas = [
        crear(cliente, borrador, cuerpo(), otro),
        editar(cliente, sesion, {"title": "Otro título"}, otro),
        eliminar(cliente, sesion, otro),
    ]

    assert [r.status_code for r in respuestas] == [404, 404, 404]
    assert list(repos.eventos.sesiones.values()) == [sesion]


def test_el_admin_gestiona_sesiones_de_eventos_ajenos(cliente, repos, auth):
    evento = repos.evento(EstadoEvento.DRAFT, ORGANIZADOR)

    creada = crear(cliente, evento, cuerpo(), auth(ADMIN))
    assert creada.status_code == 201
    sesion = repos.eventos.sesiones[next(iter(repos.eventos.sesiones))]
    editada = editar(cliente, sesion, {"title": "Otro título"}, auth(ADMIN))
    eliminada = eliminar(cliente, sesion, auth(ADMIN))

    assert editada.status_code == 200
    assert editada.json()["title"] == "Otro título"
    assert eliminada.status_code == 204
    assert repos.eventos.sesiones == {}


def test_una_sesion_que_no_existe_responde_404(cliente, repos, auth):
    falsa = Sesion(id=uuid4(), event_id=uuid4(), title="Nada", start_at=DIA, end_at=DIA)

    respuestas = [
        editar(cliente, falsa, {"title": "Otro título"}, auth(ADMIN)),
        eliminar(cliente, falsa, auth(ADMIN)),
    ]

    assert [r.status_code for r in respuestas] == [404, 404]


# --- Editar y eliminar ---------------------------------------------------------------------


def test_editar_cambia_solo_lo_que_manda_y_reemplaza_los_ponentes(cliente, repos, auth):
    evento = repos.evento()
    ana, beto = repos.ponente("Ana Pérez"), repos.ponente("Beto Ruiz")
    sesion = repos.sesion(evento, hora(9), hora(10), ana, room="Sala A", capacity=30)

    respuesta = editar(
        cliente,
        sesion,
        {"title": "  Pytest avanzado ", "speaker_ids": [str(beto.id)]},
        auth(ORGANIZADOR),
    )

    assert respuesta.status_code == 200, respuesta.text
    editada = respuesta.json()
    assert (editada["title"], editada["room"], editada["capacity"]) == (
        "Pytest avanzado",
        "Sala A",
        30,
    )
    assert [p["full_name"] for p in editada["speakers"]] == ["Beto Ruiz"]
    assert repos.sesiones.vinculos[sesion.id] == [beto.id]


def test_editar_sin_speaker_ids_conserva_los_ponentes(cliente, repos, auth):
    evento = repos.evento()
    ana = repos.ponente()
    sesion = repos.sesion(evento, hora(9), hora(10), ana)

    respuesta = editar(cliente, sesion, {"room": "Sala C"}, auth(ORGANIZADOR))

    assert respuesta.status_code == 200
    assert [p["full_name"] for p in respuesta.json()["speakers"]] == ["Ana Pérez"]
    assert repos.sesiones.vinculos[sesion.id] == [ana.id]


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"title": None}, "title"),
        ({"start_at": None}, "start_at"),
        ({"end_at": hora(8, 30).isoformat()}, "end_at"),
        ({"start_at": hora(10).isoformat()}, "end_at"),
        ({"capacity": 101}, "capacity"),
        ({"speaker_ids": [str(uuid4())]}, "speaker_ids"),
        ({"title": "Testing\x00"}, "title"),
    ],
    ids=[
        "titulo-nulo",
        "inicio-nulo",
        "fin-antes-del-inicio-guardado",
        "inicio-despues-del-fin-guardado",
        "capacidad-mayor-que-la-del-evento",
        "ponente-inexistente",
        "titulo-con-caracter-nulo",
    ],
)
def test_una_edicion_invalida_responde_422(cliente, repos, auth, cambios, campo):
    evento = repos.evento(capacity=100)
    sesion = repos.sesion(evento, hora(9), hora(10))

    respuesta = editar(cliente, sesion, cambios, auth(ORGANIZADOR))

    assert respuesta.status_code == 422
    assert [e["field"] for e in respuesta.json()["errors"]] == [campo]
    assert (sesion.title, sesion.start_at, sesion.end_at) == (
        "Testing en Python",
        hora(9),
        hora(10),
    )


def mandar(como: str, cliente, repos, datos: dict, headers: dict):
    evento = repos.evento()
    if como == "crear":
        return crear(cliente, evento, cuerpo() | datos, headers)
    return editar(cliente, repos.sesion(evento, hora(9), hora(10)), datos, headers)


@pytest.mark.parametrize("como", ["crear", "editar"])
def test_mas_de_20_ponentes_responde_422_en_speaker_ids(cliente, repos, auth, como):
    ids = [str(repos.ponente(f"Ponente {i}").id) for i in range(21)]

    respuesta = mandar(como, cliente, repos, {"speaker_ids": ids}, auth(ORGANIZADOR))

    assert respuesta.status_code == 422
    assert respuesta.json()["errors"] == [
        {"field": "speaker_ids", "message": "Debe tener como máximo 20 elementos"}
    ]


@pytest.mark.parametrize("como", ["crear", "editar"])
def test_20_ponentes_se_aceptan(cliente, repos, auth, como):
    ids = [str(repos.ponente(f"Ponente {i}").id) for i in range(20)]

    respuesta = mandar(como, cliente, repos, {"speaker_ids": ids}, auth(ORGANIZADOR))

    assert respuesta.status_code in (200, 201), respuesta.text
    assert len(respuesta.json()["speakers"]) == 20


def test_el_dueno_elimina_una_sesion(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento, hora(9), hora(10), repos.ponente())

    respuesta = eliminar(cliente, sesion, auth(ORGANIZADOR))

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert repos.eventos.sesiones == {}
    assert repos.sesiones.vinculos == {}


# --- Concurrencia: qué se bloquea y en qué orden -------------------------------------------


def test_crear_bloquea_el_evento_y_despues_los_ponentes_en_orden_de_id(cliente, repos, auth):
    evento = repos.evento()
    ponentes = [repos.ponente(f"Ponente {i}") for i in range(4)]
    desordenados = sorted(ponentes, key=lambda p: p.full_name, reverse=True)

    respuesta = crear(cliente, evento, cuerpo(*desordenados), auth(ORGANIZADOR))

    assert respuesta.status_code == 201
    assert repos.eventos.bloqueos == [evento.id, *sorted(p.id for p in ponentes)]


def test_editar_bloquea_evento_sesion_y_ponentes_en_ese_orden(cliente, repos, auth):
    evento = repos.evento()
    ana, beto = repos.ponente("Ana Pérez"), repos.ponente("Beto Ruiz")
    sesion = repos.sesion(evento, hora(9), hora(10), beto, ana)

    respuesta = editar(cliente, sesion, {"end_at": hora(10, 30).isoformat()}, auth(ORGANIZADOR))

    assert respuesta.status_code == 200
    assert repos.eventos.bloqueos == [evento.id, sesion.id, *sorted([ana.id, beto.id])]


# --- 1. Dentro del evento ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [
        (INICIO_EVENTO - timedelta(minutes=1), INICIO_EVENTO + timedelta(hours=1)),
        (FIN_EVENTO - timedelta(hours=1), FIN_EVENTO + timedelta(minutes=1)),
        (INICIO_EVENTO - timedelta(hours=2), INICIO_EVENTO - timedelta(hours=1)),
    ],
    ids=["empieza-antes", "termina-despues", "toda-antes"],
)
def test_una_sesion_fuera_del_evento_responde_409(cliente, repos, auth, inicio, fin):
    evento = repos.evento()
    datos = cuerpo(start_at=inicio.isoformat(), end_at=fin.isoformat())

    respuesta = crear(cliente, evento, datos, auth(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.json()["type"] == "session-outside-event"
    assert repos.eventos.sesiones == {}


def test_una_sesion_que_ocupa_el_evento_entero_se_acepta(cliente, repos, auth):
    evento = repos.evento()
    datos = cuerpo(start_at=INICIO_EVENTO.isoformat(), end_at=FIN_EVENTO.isoformat())

    assert crear(cliente, evento, datos, auth(ORGANIZADOR)).status_code == 201


def test_editar_una_sesion_para_que_salga_del_evento_responde_409(cliente, repos, auth):
    evento = repos.evento()
    sesion = repos.sesion(evento, hora(9), hora(10))
    tarde = (FIN_EVENTO + timedelta(hours=1)).isoformat()

    respuesta = editar(cliente, sesion, {"end_at": tarde}, auth(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "session-outside-event"
    assert sesion.end_at == hora(10)


# --- 2. Ponente sin cruces, en cualquier evento --------------------------------------------


def test_un_ponente_no_puede_estar_en_dos_sesiones_que_se_cruzan_en_otro_evento(
    cliente, repos, auth
):
    otro_evento = repos.evento(dueno=ADMIN)
    ana = repos.ponente("Ana Pérez")
    repos.sesion(otro_evento, hora(10), hora(11), ana, title="Testing en Python")
    evento = repos.evento()

    datos = cuerpo(ana, title="Otra charla", start_at=hora(10, 30).isoformat())
    datos["end_at"] = hora(11, 30).isoformat()
    respuesta = crear(cliente, evento, datos, auth(ORGANIZADOR))

    assert respuesta.status_code == 409
    problema = respuesta.json()
    assert problema["type"] == "speaker-conflict"
    # El horario de la sesión que choca, en hora de Bogotá.
    assert problema["detail"] == "Ana Pérez ya está en «Testing en Python», 10:00 a 11:00"
    assert len(repos.eventos.sesiones) == 1


# Quien asigna eligió a la ponente: su nombre se puede mostrar, la otra sesión no.
DETALLE_SIN_SESION = "Ana Pérez ya tiene otra sesión en ese horario"


def test_el_choque_con_un_borrador_ajeno_responde_409_sin_nombrar_la_sesion(cliente, repos, auth):
    borrador = repos.evento(EstadoEvento.DRAFT, dueno=OTRO_ORGANIZADOR)
    ana = repos.ponente("Ana Pérez")
    repos.sesion(borrador, hora(10), hora(11), ana, title="Lanzamiento producto X")
    evento = repos.evento()

    respuesta = crear(cliente, evento, cuerpo(ana, title="Otra charla"), auth(ORGANIZADOR))

    assert respuesta.status_code == 409
    problema = respuesta.json()
    assert problema["type"] == "speaker-conflict"
    assert problema["detail"] == DETALLE_SIN_SESION
    # Ni el título ni el horario del borrador salen en ningún lado de la respuesta.
    assert "Lanzamiento producto X" not in respuesta.text
    assert "10:00" not in respuesta.text
    assert len(repos.eventos.sesiones) == 1


def test_al_editar_el_choque_con_un_borrador_ajeno_tampoco_nombra_la_sesion(cliente, repos, auth):
    borrador = repos.evento(EstadoEvento.DRAFT, dueno=OTRO_ORGANIZADOR)
    ana = repos.ponente("Ana Pérez")
    repos.sesion(borrador, hora(10), hora(11), ana, title="Lanzamiento producto X")
    evento = repos.evento()
    sesion = repos.sesion(evento, hora(14), hora(15), ana, title="Otra charla")

    respuesta = editar(cliente, sesion, {"start_at": hora(10, 30).isoformat()}, auth(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == DETALLE_SIN_SESION
    assert "Lanzamiento producto X" not in respuesta.text


@pytest.mark.parametrize("usuario", [ADMIN, OTRO_ORGANIZADOR], ids=["admin", "dueno-del-borrador"])
def test_quien_ve_el_borrador_recibe_el_choque_con_la_sesion(cliente, repos, auth, usuario):
    borrador = repos.evento(EstadoEvento.DRAFT, dueno=OTRO_ORGANIZADOR)
    ana = repos.ponente("Ana Pérez")
    repos.sesion(borrador, hora(10), hora(11), ana, title="Lanzamiento producto X")
    evento = repos.evento(dueno=OTRO_ORGANIZADOR)

    respuesta = crear(cliente, evento, cuerpo(ana, title="Otra charla"), auth(usuario))

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == (
        "Ana Pérez ya está en «Lanzamiento producto X», 10:00 a 11:00"
    )


def test_el_choque_con_un_evento_publicado_ajeno_nombra_la_sesion(cliente, repos, auth):
    publicado = repos.evento(EstadoEvento.PUBLISHED, dueno=OTRO_ORGANIZADOR)
    ana = repos.ponente("Ana Pérez")
    repos.sesion(publicado, hora(10), hora(11), ana, title="Keynote")
    evento = repos.evento()

    respuesta = crear(cliente, evento, cuerpo(ana, title="Otra charla"), auth(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Ana Pérez ya está en «Keynote», 10:00 a 11:00"


def test_si_chocan_varios_ponentes_el_detail_lista_uno_por_linea_segun_lo_que_se_ve(
    cliente, repos, auth
):
    publicado = repos.evento(EstadoEvento.PUBLISHED, dueno=OTRO_ORGANIZADOR)
    borrador = repos.evento(EstadoEvento.DRAFT, dueno=OTRO_ORGANIZADOR)
    beto, ana = repos.ponente("Beto Ruiz"), repos.ponente("Ana Pérez")
    # Beto tiene el id menor y su sesión empieza antes: el orden de las líneas es por nombre,
    # no por id ni por horario.
    beto.id, ana.id = UUID(int=1), UUID(int=2)
    repos.ponentes.ponentes = {beto.id: beto, ana.id: ana}
    repos.sesion(borrador, hora(9, 30), hora(10, 30), beto, title="Lanzamiento producto X")
    repos.sesion(publicado, hora(10), hora(11), ana, title="Keynote")
    evento = repos.evento()

    respuesta = crear(cliente, evento, cuerpo(beto, ana, title="Otra charla"), auth(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "speaker-conflict"
    assert respuesta.json()["detail"] == (
        "Ana Pérez ya está en «Keynote», 10:00 a 11:00\n"
        "Beto Ruiz ya tiene otra sesión en ese horario"
    )
    assert "Lanzamiento producto X" not in respuesta.text


def test_el_choque_de_ponente_se_pide_a_la_base_con_el_horario_y_sin_la_agenda_entera(
    cliente, repos, auth
):
    evento = repos.evento()
    ana, beto = repos.ponente("Ana Pérez"), repos.ponente("Beto Ruiz")
    datos = cuerpo(ana, beto, start_at=hora(10, 30).isoformat(), end_at=hora(11, 30).isoformat())

    respuesta = crear(cliente, evento, datos, auth(ORGANIZADOR))

    assert respuesta.status_code == 201, respuesta.text
    assert repos.sesiones.consultas_de_choque == [
        {
            "ids_ponente": sorted([ana.id, beto.id]),
            "inicio": hora(10, 30),
            "fin": hora(11, 30),
            "excluir": None,
        }
    ]


def test_al_editar_el_choque_se_pide_con_el_horario_nuevo_y_excluyendo_la_propia_sesion(
    cliente, repos, auth
):
    evento = repos.evento()
    ana = repos.ponente()
    sesion = repos.sesion(evento, hora(10), hora(11), ana)

    respuesta = editar(cliente, sesion, {"end_at": hora(12).isoformat()}, auth(ORGANIZADOR))

    assert respuesta.status_code == 200, respuesta.text
    assert repos.sesiones.consultas_de_choque == [
        {"ids_ponente": [ana.id], "inicio": hora(10), "fin": hora(12), "excluir": sesion.id}
    ]


def test_el_cruce_de_ponente_se_revisa_para_cada_ponente(cliente, repos, auth):
    evento = repos.evento()
    ana, beto = repos.ponente("Ana Pérez"), repos.ponente("Beto Ruiz")
    repos.sesion(evento, hora(10), hora(11), beto, title="Rust", room="Sala A")

    respuesta = crear(cliente, evento, cuerpo(ana, beto, room="Sala B"), auth(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Beto Ruiz ya está en «Rust», 10:00 a 11:00"


def test_terminar_a_las_10_y_empezar_a_las_10_no_es_cruce(cliente, repos, auth):
    evento = repos.evento()
    ana = repos.ponente()
    repos.sesion(evento, hora(9), hora(10), ana, room="Sala B")

    respuesta = crear(
        cliente,
        evento,
        cuerpo(ana, start_at=hora(10).isoformat(), end_at=hora(11).isoformat()),
        auth(ORGANIZADOR),
    )

    assert respuesta.status_code == 201, respuesta.text


def test_una_sesion_de_un_evento_cancelado_no_ocupa_al_ponente(cliente, repos, auth):
    cancelado = repos.evento(EstadoEvento.CANCELLED)
    ana = repos.ponente()
    repos.sesion(cancelado, hora(10), hora(11), ana)
    evento = repos.evento()

    respuesta = crear(cliente, evento, cuerpo(ana), auth(ORGANIZADOR))

    assert respuesta.status_code == 201, respuesta.text


def test_al_editar_una_sesion_no_choca_consigo_misma(cliente, repos, auth):
    evento = repos.evento()
    ana = repos.ponente()
    sesion = repos.sesion(evento, hora(10), hora(11), ana, room="Sala B")

    respuesta = editar(
        cliente,
        sesion,
        {"start_at": hora(10, 30).isoformat(), "end_at": hora(11, 30).isoformat()},
        auth(ORGANIZADOR),
    )

    assert respuesta.status_code == 200, respuesta.text
    assert sesion.start_at == hora(10, 30)


def test_editar_hacia_el_horario_de_otra_sesion_del_ponente_responde_409(cliente, repos, auth):
    evento = repos.evento()
    ana = repos.ponente()
    repos.sesion(evento, hora(10), hora(11), ana, title="Testing en Python")
    sesion = repos.sesion(evento, hora(14), hora(15), ana, title="Pytest avanzado")

    respuesta = editar(cliente, sesion, {"start_at": hora(10, 45).isoformat()}, auth(ADMIN))

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "speaker-conflict"
    assert sesion.start_at == hora(14)


def test_asignar_un_ponente_ocupado_al_editar_responde_409(cliente, repos, auth):
    evento = repos.evento()
    ana, beto = repos.ponente("Ana Pérez"), repos.ponente("Beto Ruiz")
    repos.sesion(evento, hora(10), hora(11), beto, title="Rust", room="Sala A")
    sesion = repos.sesion(evento, hora(10), hora(11), ana, room="Sala B")

    respuesta = editar(cliente, sesion, {"speaker_ids": [str(beto.id)]}, auth(ORGANIZADOR))

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "speaker-conflict"
    assert repos.sesiones.vinculos[sesion.id] == [ana.id]


# --- 3 y 4. Sala sin cruces en el mismo evento; salas distintas, en paralelo ----------------


def test_la_misma_sala_sin_mayusculas_ni_espacios_se_cruza(cliente, repos, auth):
    evento = repos.evento()
    repos.sesion(evento, hora(10), hora(11), room="Sala B")

    respuesta = crear(
        cliente,
        evento,
        cuerpo(room=" sala b ", start_at=hora(10, 30).isoformat(), end_at=hora(11, 30).isoformat()),
        auth(ORGANIZADOR),
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "room-conflict"
    assert len(repos.eventos.sesiones) == 1


@pytest.mark.parametrize(
    ("sala_existente", "sala_nueva"),
    [("Sala A", "Sala B"), (None, None), ("Sala B", None)],
    ids=["salas-distintas", "sin-sala", "una-sin-sala"],
)
def test_sesiones_paralelas_que_no_comparten_sala_se_aceptan(
    cliente, repos, auth, sala_existente, sala_nueva
):
    evento = repos.evento()
    repos.sesion(evento, hora(10), hora(11), room=sala_existente)

    respuesta = crear(cliente, evento, cuerpo(room=sala_nueva), auth(ORGANIZADOR))

    assert respuesta.status_code == 201, respuesta.text


def test_la_misma_sala_en_otro_evento_no_choca(cliente, repos, auth):
    repos.sesion(repos.evento(), hora(10), hora(11), room="Sala B")
    evento = repos.evento()

    assert crear(cliente, evento, cuerpo(room="Sala B"), auth(ORGANIZADOR)).status_code == 201


def test_la_misma_sala_una_despues_de_otra_no_choca(cliente, repos, auth):
    evento = repos.evento()
    repos.sesion(evento, hora(9), hora(10), room="Sala B")

    assert crear(cliente, evento, cuerpo(room="Sala B"), auth(ORGANIZADOR)).status_code == 201


def test_al_editar_la_sala_no_choca_consigo_misma_pero_si_con_otra(cliente, repos, auth):
    evento = repos.evento()
    repos.sesion(evento, hora(12), hora(13), room="Sala B", title="Rust")
    sesion = repos.sesion(evento, hora(10), hora(11), room="Sala B")

    corrida = editar(cliente, sesion, {"end_at": hora(11, 30).isoformat()}, auth(ORGANIZADOR))
    pisada = editar(cliente, sesion, {"end_at": hora(12, 30).isoformat()}, auth(ORGANIZADOR))

    assert corrida.status_code == 200, corrida.text
    assert pisada.status_code == 409
    assert pisada.json()["type"] == "room-conflict"
    assert sesion.end_at == hora(11, 30)


# --- 6. Un evento cancelado o finalizado no acepta sesiones nuevas ni cambios --------------


def evento_terminado(repos):
    ayer = datetime.now(UTC) - timedelta(days=1)
    return repos.evento(start_at=ayer - timedelta(hours=8), end_at=ayer)


@pytest.mark.parametrize("como", ["cancelado", "finalizado"])
def test_un_evento_cancelado_o_finalizado_no_acepta_sesiones_ni_cambios(cliente, repos, auth, como):
    if como == "cancelado":
        evento = repos.evento(EstadoEvento.CANCELLED)
        inicio, fin = hora(9), hora(10)
    else:
        evento = evento_terminado(repos)
        inicio, fin = evento.start_at, evento.start_at + timedelta(hours=1)
    sesion = repos.sesion(evento, inicio, fin)
    datos = cuerpo(start_at=inicio.isoformat(), end_at=fin.isoformat(), room=None)

    respuestas = [
        crear(cliente, evento, datos, auth(ORGANIZADOR)),
        editar(cliente, sesion, {"title": "Otro título"}, auth(ORGANIZADOR)),
        eliminar(cliente, sesion, auth(ADMIN)),
    ]

    assert [r.status_code for r in respuestas] == [409, 409, 409]
    assert {r.json()["type"] for r in respuestas} == {"conflict"}
    assert list(repos.eventos.sesiones.values()) == [sesion]
    assert sesion.title == "Testing en Python"
