"""Gestión de usuarios por el admin: listar, cambiar el rol y activar o desactivar."""

import secrets
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.api.dependencias import repositorio_usuarios
from app.core.contrasenas import hashear
from app.core.excepciones import Conflict, Forbidden, NotFound
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.usuario import User
from app.repositories.usuarios import RepositorioUsuarios
from app.schemas.administracion import FiltrosUsuarios, UsuarioEdicion
from app.services import administracion
from tests.unit.dobles import RepositorioUsuariosFalso

CREADO = datetime(2026, 10, 1, 12, tzinfo=UTC)
HASH = hashear(secrets.token_urlsafe())


def nuevo(email: str, rol: Rol, *, activo: bool = True) -> User:
    return User(
        email=email,
        password_hash=HASH,
        role=rol,
        is_active=activo,
        full_name=email.split("@")[0].title(),
        created_at=CREADO,
        updated_at=CREADO,
    )


@pytest.fixture
def gente() -> dict[str, User]:
    return {
        "admin": nuevo("admin@mail.com", Rol.ADMIN),
        "otro_admin": nuevo("otro.admin@mail.com", Rol.ADMIN),
        "orga": nuevo("orga@mail.com", Rol.ORGANIZER),
        "ana": nuevo("ana@mail.com", Rol.ATTENDEE),
    }


@pytest.fixture
def repo(app, gente) -> RepositorioUsuariosFalso:
    repo = RepositorioUsuariosFalso(*gente.values())
    app.dependency_overrides[repositorio_usuarios] = lambda: repo
    return repo


@pytest.fixture
def auth(settings):
    def de(usuario: User) -> dict:
        token = crear_access_token(usuario.id, settings.jwt_secret, 5)
        return {"Authorization": f"Bearer {token}"}

    return de


def patch(cliente, auth, actor: User, id_usuario, cuerpo: dict):
    return cliente.patch(f"/admin/users/{id_usuario}", json=cuerpo, headers=auth(actor))


# --- PATCH: qué campos acepta ----------------------------------------------------------------


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"full_name": "Otro Nombre"},
        {"email": "nuevo@mail.com"},
        {"password": secrets.token_urlsafe()},
        {"role": "ATTENDEE", "full_name": "Otro Nombre"},
        {"must_change_password": True},
    ],
)
def test_un_patch_con_un_campo_que_no_es_rol_ni_estado_responde_422(
    cliente, repo, auth, gente, cuerpo
):
    orga = gente["orga"]

    respuesta = patch(cliente, auth, gente["admin"], orga.id, cuerpo)

    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.headers["content-type"] == "application/problem+json"
    rechazados = {e["field"] for e in respuesta.json()["errors"]}
    assert rechazados == set(cuerpo) - {"role"}
    assert (orga.role, orga.full_name, orga.email) == (Rol.ORGANIZER, "Orga", "orga@mail.com")
    assert repo.operaciones == []


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        ({"role": None}, "role"),
        ({"is_active": None}, "is_active"),
        ({"role": "SUPERUSER"}, "role"),
        ({"is_active": "talvez"}, "is_active"),
    ],
)
def test_un_rol_o_estado_invalido_o_nulo_responde_422(cliente, repo, auth, gente, cuerpo, campo):
    respuesta = patch(cliente, auth, gente["admin"], gente["orga"].id, cuerpo)

    assert respuesta.status_code == 422, respuesta.text
    assert [e["field"] for e in respuesta.json()["errors"]] == [campo]
    assert repo.operaciones == []


def test_el_admin_cambia_el_rol_y_recibe_el_usuario_con_sus_inscripciones(
    cliente, repo, auth, gente
):
    ana = gente["ana"]
    repo.inscripciones[ana.id] = 3

    respuesta = patch(cliente, auth, gente["admin"], ana.id, {"role": "ORGANIZER"})

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["id"] == str(ana.id)
    assert cuerpo["role"] == "ORGANIZER"
    assert cuerpo["is_active"] is True
    assert cuerpo["active_registrations"] == 3
    assert set(cuerpo) == {
        "id",
        "email",
        "full_name",
        "role",
        "is_active",
        "must_change_password",
        "created_at",
        "updated_at",
        "active_registrations",
    }
    assert "password_hash" not in respuesta.text
    assert ana.role == Rol.ORGANIZER


def test_el_admin_desactiva_y_reactiva_a_un_usuario(cliente, repo, auth, gente):
    orga = gente["orga"]

    desactivado = patch(cliente, auth, gente["admin"], orga.id, {"is_active": False})
    assert desactivado.status_code == 200, desactivado.text
    assert desactivado.json()["is_active"] is False
    assert orga.is_active is False

    reactivado = patch(cliente, auth, gente["admin"], orga.id, {"is_active": True})
    assert reactivado.status_code == 200, reactivado.text
    assert orga.is_active is True


def test_un_usuario_inexistente_responde_404(cliente, repo, auth, gente):
    inexistente = uuid4()

    respuesta = patch(cliente, auth, gente["admin"], inexistente, {"role": "ADMIN"})

    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"] == "application/problem+json"
    # El 404 es porque se lo buscó y no está, no porque la ruta no exista.
    assert ("leer para escribir", inexistente) in repo.operaciones


# --- Permisos ----------------------------------------------------------------------------------


@pytest.mark.parametrize("quien", ["orga", "ana"])
def test_sin_el_permiso_los_dos_endpoints_responden_403(cliente, repo, auth, gente, quien):
    actor = gente[quien]

    listado = cliente.get("/admin/users", headers=auth(actor))
    cambio = patch(cliente, auth, actor, gente["ana"].id, {"role": "ADMIN"})

    assert (listado.status_code, cambio.status_code) == (403, 403)
    assert listado.json()["type"] == cambio.json()["type"] == "forbidden"
    assert gente["ana"].role == Rol.ATTENDEE
    assert repo.busquedas == []
    assert repo.operaciones == []


def test_sin_token_los_dos_endpoints_responden_401(cliente, repo, gente):
    listado = cliente.get("/admin/users")
    cambio = cliente.patch(f"/admin/users/{gente['ana'].id}", json={"role": "ADMIN"})

    assert (listado.status_code, cambio.status_code) == (401, 401)


# --- Protecciones, en el servicio -----------------------------------------------------------


def test_sin_permiso_es_403_aunque_el_usuario_no_exista(repo, gente):
    with pytest.raises(Forbidden):
        administracion.cambiar(repo, gente["orga"], uuid4(), UsuarioEdicion(role=Rol.ADMIN))

    assert repo.operaciones == []


def test_listar_sin_permiso_es_403_sin_buscar(repo, gente):
    with pytest.raises(Forbidden):
        administracion.listar(repo, gente["ana"], FiltrosUsuarios(), 0, 12)

    assert repo.busquedas == []


@pytest.mark.parametrize(
    "cambio",
    [{"role": Rol.ORGANIZER}, {"role": Rol.ATTENDEE}, {"is_active": False}],
    ids=["a-organizador", "a-asistente", "desactivarse"],
)
def test_el_admin_no_puede_cambiarse_el_rol_ni_desactivarse(repo, gente, cambio):
    admin = gente["admin"]

    with pytest.raises(Conflict) as error:
        administracion.cambiar(repo, admin, admin.id, UsuarioEdicion(**cambio))

    assert error.value.tipo == "cannot-modify-self"
    assert error.value.status == 409
    assert error.value.titulo == "No podés cambiarte el rol ni desactivarte a vos mismo"
    assert (admin.role, admin.is_active) == (Rol.ADMIN, True)
    assert repo.operaciones == []  # se corta antes de bloquear a nadie


def test_el_409_cannot_modify_self_llega_como_problem_json(cliente, repo, auth, gente):
    admin = gente["admin"]

    respuesta = patch(cliente, auth, admin, admin.id, {"role": "ATTENDEE"})

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert cuerpo["type"] == "cannot-modify-self"
    assert cuerpo["title"] == "No podés cambiarte el rol ni desactivarte a vos mismo"
    assert cuerpo["trace_id"]


@pytest.mark.parametrize(
    "cambio",
    [{"role": Rol.ORGANIZER}, {"is_active": False}],
    ids=["degradar", "desactivar"],
)
def test_bloquea_a_todos_los_admins_activos_antes_de_leer_y_guardar(repo, gente, cambio):
    admin, otro = gente["admin"], gente["otro_admin"]

    administracion.cambiar(repo, admin, otro.id, UsuarioEdicion(**cambio))

    bloqueados = sorted([admin.id, otro.id])
    assert repo.operaciones == [
        ("bloquear", frozenset({Rol.ADMIN}), bloqueados),
        ("leer para escribir", otro.id),
        ("guardar", otro.id),
    ]


def test_con_dos_admins_uno_degrada_al_otro(repo, gente):
    admin, otro = gente["admin"], gente["otro_admin"]

    resultado = administracion.cambiar(repo, admin, otro.id, UsuarioEdicion(role=Rol.ATTENDEE))

    assert resultado.usuario is otro
    assert otro.role == Rol.ATTENDEE


def test_degradar_o_desactivar_al_ultimo_admin_activo_es_409_last_admin(gente):
    """Lo que pasa cuando otro admin degradó a este en paralelo: el actor llegó con su usuario
    leído antes del bloqueo (todavía admin), pero en la base ya no lo es."""
    otro = gente["otro_admin"]
    actor_en_memoria = gente["admin"]
    actor_en_la_base = nuevo("admin@mail.com", Rol.ATTENDEE)
    actor_en_la_base.id = actor_en_memoria.id
    repo = RepositorioUsuariosFalso(actor_en_la_base, otro)

    for cambio in ({"role": Rol.ORGANIZER}, {"is_active": False}):
        with pytest.raises(Conflict) as error:
            administracion.cambiar(repo, actor_en_memoria, otro.id, UsuarioEdicion(**cambio))

        assert error.value.tipo == "last-admin"
        assert error.value.titulo == "Tiene que quedar al menos un administrador activo"
    assert (otro.role, otro.is_active) == (Rol.ADMIN, True)
    assert not any(op[0] == "guardar" for op in repo.operaciones)


def test_lo_que_no_saca_a_un_admin_activo_pasa_aunque_quede_uno_solo(gente):
    """La regla del último admin es sobre los admins activos: tocar a un admin inactivo, a
    quien no es admin, o promover, pasa aunque haya un solo admin activo."""
    admin = gente["admin"]
    inactivo = nuevo("viejo.admin@mail.com", Rol.ADMIN, activo=False)
    orga = gente["orga"]
    repo = RepositorioUsuariosFalso(admin, inactivo, orga)

    administracion.cambiar(repo, admin, inactivo.id, UsuarioEdicion(role=Rol.ATTENDEE))
    administracion.cambiar(repo, admin, orga.id, UsuarioEdicion(is_active=False))
    administracion.cambiar(repo, admin, orga.id, UsuarioEdicion(role=Rol.ADMIN))

    assert inactivo.role == Rol.ATTENDEE
    assert (orga.role, orga.is_active) == (Rol.ADMIN, False)


def test_un_admin_activo_que_sigue_siendo_admin_activo_no_choca_con_el_ultimo_admin(gente):
    admin = gente["admin"]
    otro = gente["otro_admin"]
    actor_en_la_base = nuevo("admin@mail.com", Rol.ATTENDEE)
    actor_en_la_base.id = admin.id
    repo = RepositorioUsuariosFalso(actor_en_la_base, otro)

    resultado = administracion.cambiar(
        repo, admin, otro.id, UsuarioEdicion(role=Rol.ADMIN, is_active=True)
    )

    assert resultado.usuario is otro
    assert [op[0] for op in repo.operaciones] == ["bloquear", "leer para escribir", "guardar"]


def test_un_usuario_inexistente_es_not_found_despues_de_bloquear(repo, gente):
    with pytest.raises(NotFound):
        administracion.cambiar(repo, gente["admin"], uuid4(), UsuarioEdicion(role=Rol.ADMIN))

    assert [op[0] for op in repo.operaciones] == ["bloquear", "leer para escribir"]


# --- Listado -----------------------------------------------------------------------------------


def test_los_filtros_llegan_a_la_busqueda_y_se_cuenta_la_pagina_de_una_vez(
    cliente, repo, auth, gente
):
    params = {"q": "an_a%", "role": "ATTENDEE", "is_active": "false", "page": 1, "page_size": 3}

    respuesta = cliente.get("/admin/users", params=params, headers=auth(gente["admin"]))

    assert respuesta.status_code == 200, respuesta.text
    [busqueda] = repo.busquedas
    assert busqueda["filtros"] == FiltrosUsuarios(q="an_a%", rol=Rol.ATTENDEE, activo=False)
    assert (busqueda["offset"], busqueda["limite"]) == (0, 3)
    cuerpo = respuesta.json()
    assert (cuerpo["total"], cuerpo["page"], cuerpo["page_size"], cuerpo["pages"]) == (4, 1, 3, 2)
    pagina = [gente[k].id for k in ("admin", "otro_admin", "orga")]
    assert repo.conteos == [pagina]
    assert [u["id"] for u in cuerpo["items"]] == [str(id_) for id_ in pagina]


def test_cada_usuario_del_listado_trae_sus_inscripciones_activas(cliente, repo, auth, gente):
    repo.inscripciones[gente["ana"].id] = 2

    respuesta = cliente.get("/admin/users", headers=auth(gente["admin"]))

    assert respuesta.status_code == 200, respuesta.text
    por_email = {u["email"]: u for u in respuesta.json()["items"]}
    assert por_email["ana@mail.com"]["active_registrations"] == 2
    assert por_email["ana@mail.com"]["role"] == "ATTENDEE"
    assert por_email["orga@mail.com"]["active_registrations"] == 0
    assert len(repo.conteos) == 1


def test_sin_parametros_busca_sin_filtros_desde_la_primera_pagina(cliente, repo, auth, gente):
    respuesta = cliente.get("/admin/users", headers=auth(gente["admin"]))

    assert respuesta.status_code == 200
    [busqueda] = repo.busquedas
    assert busqueda["filtros"] == FiltrosUsuarios()
    assert (busqueda["offset"], busqueda["limite"]) == (0, 12)


@pytest.mark.parametrize(
    ("params", "campo"),
    [
        ({"role": "SUPERUSER"}, "role"),
        ({"is_active": "talvez"}, "is_active"),
        ({"q": "x" * 101}, "q"),
        ({"page": 0}, "page"),
    ],
)
def test_un_filtro_invalido_responde_422(cliente, repo, auth, gente, params, campo):
    respuesta = cliente.get("/admin/users", params=params, headers=auth(gente["admin"]))

    assert respuesta.status_code == 422
    assert [e["field"] for e in respuesta.json()["errors"]] == [campo]
    assert repo.busquedas == []


# --- El repositorio bloquea a los admins activos en orden ----------------------------------


class SesionQueAnota:
    def __init__(self) -> None:
        self.consultas: list = []

    def exec(self, consulta):
        self.consultas.append(consulta)
        return self

    def all(self) -> list:
        return []


def test_el_repositorio_bloquea_los_activos_de_esos_roles_por_id_y_los_relee():
    sesion = SesionQueAnota()

    RepositorioUsuarios(sesion).activos_para_escribir([Rol.ADMIN])

    assert len(sesion.consultas) == 1
    [consulta] = sesion.consultas
    sql = str(consulta.compile(dialect=postgresql.dialect())).replace("\n", " ")
    assert "FOR UPDATE" in sql
    assert "ORDER BY users.id" in sql
    assert "users.is_active" in sql
    assert "users.role IN" in sql
    assert consulta.get_execution_options().get("populate_existing") is True
