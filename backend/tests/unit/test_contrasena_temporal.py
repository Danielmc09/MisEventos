"""El admin crea usuarios y les restablece la contraseña: el sistema genera una temporal, la
muestra una sola vez y obliga a cambiarla en el primer login."""

import logging
import secrets
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.api.dependencias import repositorio_usuarios
from app.core.contrasenas import hashear, verificar
from app.core.excepciones import Conflict, Forbidden
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.usuario import User
from app.schemas.administracion import UsuarioAlta
from app.services import administracion
from tests.unit.dobles import RepositorioUsuariosFalso
from tests.unit.test_contrasena_no_se_filtra import texto_de_los_logs

CREADO = datetime(2026, 10, 1, 12, tzinfo=UTC)
CLAVE_ORIGINAL = secrets.token_urlsafe()
HASH_ORIGINAL = hashear(CLAVE_ORIGINAL)


def nuevo(email: str, rol: Rol, *, activo: bool = True) -> User:
    return User(
        email=email,
        password_hash=HASH_ORIGINAL,
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


ALTA = {"email": "  Nueva.Persona@Mail.COM ", "full_name": "Nueva Persona", "role": "ORGANIZER"}


def crear(cliente, auth, actor: User, cuerpo: dict):
    return cliente.post("/admin/users", json=cuerpo, headers=auth(actor))


# --- Crear -------------------------------------------------------------------------------------


def test_el_admin_crea_un_usuario_y_recibe_la_temporal_una_sola_vez(cliente, repo, auth, gente):
    respuesta = crear(cliente, auth, gente["admin"], ALTA)

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    temporal = cuerpo["temporary_password"]
    assert len(temporal) == 16
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
        "temporary_password",
    }
    assert cuerpo["email"] == "nueva.persona@mail.com"
    assert (cuerpo["full_name"], cuerpo["role"]) == ("Nueva Persona", "ORGANIZER")
    assert (cuerpo["is_active"], cuerpo["must_change_password"]) == (True, True)
    assert cuerpo["active_registrations"] == 0
    assert "password_hash" not in respuesta.text

    [creado] = [u for u in repo.usuarios.values() if u.email == "nueva.persona@mail.com"]
    assert str(creado.id) == cuerpo["id"]
    assert creado.must_change_password is True
    assert creado.role == Rol.ORGANIZER
    # Solo el hash Argon2: la temporal en claro no queda en el usuario.
    assert creado.password_hash.startswith("$argon2id$")
    assert verificar(creado.password_hash, temporal)
    assert temporal not in creado.password_hash


def test_la_respuesta_con_la_temporal_no_se_guarda_en_ninguna_cache(cliente, repo, auth, gente):
    respuesta = crear(cliente, auth, gente["admin"], ALTA)

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"


def test_el_admin_puede_crear_otro_admin(cliente, repo, auth, gente):
    respuesta = crear(cliente, auth, gente["admin"], {**ALTA, "role": "ADMIN"})

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["role"] == "ADMIN"


def test_dos_usuarios_creados_seguidos_reciben_temporales_distintas(cliente, repo, auth, gente):
    primera = crear(cliente, auth, gente["admin"], ALTA)
    segunda = crear(cliente, auth, gente["admin"], {**ALTA, "email": "otra@mail.com"})

    assert (primera.status_code, segunda.status_code) == (201, 201)
    assert primera.json()["temporary_password"] != segunda.json()["temporary_password"]


@pytest.mark.parametrize(
    ("cuerpo", "campos"),
    [
        ({**ALTA, "password": secrets.token_urlsafe()}, {"password"}),
        ({**ALTA, "must_change_password": False}, {"must_change_password"}),
        ({**ALTA, "is_active": False}, {"is_active"}),
        ({"full_name": "Sin Email", "role": "ATTENDEE"}, {"email"}),
        ({"email": "sin.rol@mail.com", "full_name": "Sin Rol"}, {"role"}),
        ({**ALTA, "email": "no-es-un-email"}, {"email"}),
        ({**ALTA, "role": "SUPERUSER"}, {"role"}),
        ({**ALTA, "full_name": "x" * 121}, {"full_name"}),
        ({**ALTA, "full_name": "con\x00nulo"}, {"full_name"}),
    ],
    ids=[
        "con-password",
        "con-must-change",
        "con-is-active",
        "sin-email",
        "sin-rol",
        "email-invalido",
        "rol-invalido",
        "nombre-largo",
        "nombre-con-nulo",
    ],
)
def test_un_cuerpo_invalido_responde_422_sin_crear_a_nadie(
    cliente, repo, auth, gente, cuerpo, campos
):
    antes = set(repo.usuarios)

    respuesta = crear(cliente, auth, gente["admin"], cuerpo)

    assert respuesta.status_code == 422, respuesta.text
    assert {e["field"] for e in respuesta.json()["errors"]} == campos
    assert set(repo.usuarios) == antes
    assert repo.operaciones == []


def test_un_email_ya_registrado_con_otras_mayusculas_es_409_email_taken(cliente, repo, auth, gente):
    antes = set(repo.usuarios)

    respuesta = crear(cliente, auth, gente["admin"], {**ALTA, "email": " ORGA@Mail.com"})

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo["type"] == "email-taken"
    assert cuerpo["title"] == "Ese email ya está registrado"
    assert cuerpo["trace_id"]
    assert "temporary_password" not in cuerpo
    assert set(repo.usuarios) == antes
    assert gente["orga"].password_hash == HASH_ORIGINAL


def test_el_email_tomado_lo_decide_el_indice_unico_al_guardar(gente):
    """Dos admins crean el mismo email a la vez: el índice rechaza al segundo, y es un 409."""
    repo = RepositorioUsuariosFalso(gente["admin"], choca_al_guardar=True)

    with pytest.raises(Conflict) as error:
        administracion.crear(
            repo, gente["admin"], UsuarioAlta(email="z@mail.com", role=Rol.ATTENDEE)
        )

    assert error.value.tipo == "email-taken"


@pytest.mark.parametrize("quien", ["orga", "ana"])
def test_sin_el_permiso_crear_responde_403_sin_crear_a_nadie(cliente, repo, auth, gente, quien):
    antes = set(repo.usuarios)

    respuesta = crear(cliente, auth, gente[quien], ALTA)

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["type"] == "forbidden"
    assert set(repo.usuarios) == antes
    assert repo.operaciones == []


def test_sin_permiso_es_403_aunque_el_email_este_tomado(repo, gente):
    with pytest.raises(Forbidden):
        administracion.crear(repo, gente["ana"], UsuarioAlta(email="orga@mail.com", role=Rol.ADMIN))

    assert repo.operaciones == []


def test_sin_token_crear_responde_401(cliente, repo):
    assert cliente.post("/admin/users", json=ALTA).status_code == 401


def test_la_temporal_del_alta_no_queda_en_ningun_log(cliente, repo, auth, gente, caplog):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="miseventos")

    respuesta = crear(cliente, auth, gente["admin"], ALTA)

    assert respuesta.status_code == 201, respuesta.text
    temporal = respuesta.json()["temporary_password"]
    # El log del request sí se capturó; si no, la búsqueda de abajo no probaría nada.
    assert any(r.name == "miseventos.acceso" for r in caplog.records)
    assert temporal not in texto_de_los_logs(caplog)


# --- Restablecer -------------------------------------------------------------------------------


def restablecer(cliente, auth, actor: User, id_usuario):
    return cliente.post(f"/admin/users/{id_usuario}/reset-password", headers=auth(actor))


def test_el_admin_restablece_la_contrasena_y_recibe_una_temporal_nueva(cliente, repo, auth, gente):
    ana = gente["ana"]

    respuesta = restablecer(cliente, auth, gente["admin"], ana.id)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"temporary_password"}
    temporal = cuerpo["temporary_password"]
    assert len(temporal) == 16
    assert ana.must_change_password is True
    assert ana.password_hash.startswith("$argon2id$")
    assert verificar(ana.password_hash, temporal)
    # La anterior deja de servir.
    assert not verificar(ana.password_hash, CLAVE_ORIGINAL)
    assert ("guardar", ana.id) in repo.operaciones


def test_restablecer_bloquea_la_fila_antes_de_cambiarla(repo, gente):
    ana = gente["ana"]

    administracion.restablecer_contrasena(repo, gente["admin"], ana.id)

    assert repo.operaciones == [("leer para escribir", ana.id), ("guardar", ana.id)]


def test_dos_restablecimientos_seguidos_dan_temporales_distintas(repo, gente):
    ana = gente["ana"]

    primera = administracion.restablecer_contrasena(repo, gente["admin"], ana.id)
    segunda = administracion.restablecer_contrasena(repo, gente["admin"], ana.id)

    assert primera != segunda
    assert not verificar(ana.password_hash, primera)
    assert verificar(ana.password_hash, segunda)


def test_el_admin_no_se_restablece_su_propia_contrasena(cliente, repo, auth, gente):
    admin = gente["admin"]

    respuesta = restablecer(cliente, auth, admin, admin.id)

    assert respuesta.status_code == 403, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["type"] == "cannot-modify-self"
    assert cuerpo["title"] == "Para cambiar tu propia contraseña usá «Cambiar contraseña»"
    assert "temporary_password" not in cuerpo
    assert admin.password_hash == HASH_ORIGINAL
    assert admin.must_change_password is False
    assert repo.operaciones == []


def test_a_un_usuario_desactivado_no_se_le_restablece_la_contrasena(gente):
    inactivo = nuevo("baja@mail.com", Rol.ATTENDEE, activo=False)
    repo = RepositorioUsuariosFalso(gente["admin"], inactivo)

    with pytest.raises(Conflict) as error:
        administracion.restablecer_contrasena(repo, gente["admin"], inactivo.id)

    assert error.value.tipo == "user-inactive"
    assert error.value.status == 409
    assert inactivo.password_hash == HASH_ORIGINAL
    assert inactivo.must_change_password is False
    assert not any(op[0] == "guardar" for op in repo.operaciones)


def test_el_409_user_inactive_llega_como_problem_json(cliente, auth, app, gente):
    inactivo = nuevo("baja@mail.com", Rol.ATTENDEE, activo=False)
    repo = RepositorioUsuariosFalso(gente["admin"], inactivo)
    app.dependency_overrides[repositorio_usuarios] = lambda: repo

    respuesta = restablecer(cliente, auth, gente["admin"], inactivo.id)

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo["type"] == "user-inactive"
    assert cuerpo["title"] == "El usuario está desactivado: reactivalo antes"
    assert cuerpo["trace_id"]


def test_restablecer_a_un_usuario_inexistente_responde_404(cliente, repo, auth, gente):
    inexistente = uuid4()

    respuesta = restablecer(cliente, auth, gente["admin"], inexistente)

    assert respuesta.status_code == 404, respuesta.text
    assert respuesta.json()["type"] == "not-found"
    assert ("leer para escribir", inexistente) in repo.operaciones


@pytest.mark.parametrize("quien", ["orga", "ana"])
def test_sin_el_permiso_restablecer_responde_403_sin_tocar_a_nadie(
    cliente, repo, auth, gente, quien
):
    orga = gente["orga"]

    respuesta = restablecer(cliente, auth, gente[quien], orga.id)

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["type"] == "forbidden"
    assert orga.password_hash == HASH_ORIGINAL
    assert repo.operaciones == []


def test_sin_permiso_es_403_aunque_sea_uno_mismo_o_no_exista(repo, gente):
    ana = gente["ana"]

    for id_usuario in (ana.id, uuid4()):
        with pytest.raises(Forbidden) as error:
            administracion.restablecer_contrasena(repo, ana, id_usuario)
        assert error.value.tipo == "forbidden"

    assert repo.operaciones == []


def test_sin_token_restablecer_responde_401(cliente, repo, gente):
    respuesta = cliente.post(f"/admin/users/{gente['ana'].id}/reset-password")

    assert respuesta.status_code == 401


def test_la_temporal_restablecida_no_queda_en_ningun_log(cliente, repo, auth, gente, caplog):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="miseventos")

    respuesta = restablecer(cliente, auth, gente["admin"], gente["ana"].id)

    assert respuesta.status_code == 200, respuesta.text
    temporal = respuesta.json()["temporary_password"]
    assert any(r.name == "miseventos.acceso" for r in caplog.records)
    assert temporal not in texto_de_los_logs(caplog)
