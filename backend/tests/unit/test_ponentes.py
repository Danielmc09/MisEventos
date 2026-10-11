from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.api.dependencias import repositorio_ponentes, repositorio_usuarios
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.ponente import Speaker
from app.models.usuario import User
from tests.unit.dobles import RepositorioPonentesFalso, RepositorioUsuariosFalso

ASISTENTE = User(email="asistente@mail.com", password_hash="$argon2id$x", role=Rol.ATTENDEE)
ORGANIZADOR = User(email="orga@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
OTRO_ORGANIZADOR = User(email="otro@mail.com", password_hash="$argon2id$x", role=Rol.ORGANIZER)
ADMIN = User(email="admin@mail.com", password_hash="$argon2id$x", role=Rol.ADMIN)


def ponente(creador: User = ORGANIZADOR, **cambios) -> Speaker:
    datos = {"full_name": "Ana Pérez", "bio": "Testing", "email": "ana@mail.com"} | cambios
    nuevo = Speaker(**datos, created_by=creador.id)
    nuevo.created_at = nuevo.updated_at = datetime.now(UTC)
    return nuevo


@pytest.fixture
def ponentes(app) -> RepositorioPonentesFalso:
    repo = RepositorioPonentesFalso()
    usuarios = RepositorioUsuariosFalso(ASISTENTE, ORGANIZADOR, OTRO_ORGANIZADOR, ADMIN)
    app.dependency_overrides[repositorio_usuarios] = lambda: usuarios
    app.dependency_overrides[repositorio_ponentes] = lambda: repo
    return repo


@pytest.fixture
def auth(settings):
    def de(usuario: User | None) -> dict:
        if usuario is None:
            return {}
        return {"Authorization": f"Bearer {crear_access_token(usuario.id, settings.jwt_secret, 5)}"}

    return de


# --- Buscar y crear: permisos --------------------------------------------------------------


def test_un_asistente_no_busca_ni_crea_ponentes(cliente, ponentes, auth):
    busqueda = cliente.get("/speakers", headers=auth(ASISTENTE))
    creacion = cliente.post("/speakers", json={"full_name": "Ana"}, headers=auth(ASISTENTE))

    assert (busqueda.status_code, creacion.status_code) == (403, 403)
    assert busqueda.headers["content-type"] == "application/problem+json"
    assert ponentes.busquedas == []
    assert ponentes.ponentes == {}


def test_sin_token_no_se_busca_ni_se_crea(cliente, ponentes):
    busqueda = cliente.get("/speakers")
    creacion = cliente.post("/speakers", json={"full_name": "Ana"})

    assert (busqueda.status_code, creacion.status_code) == (401, 401)
    assert creacion.headers["www-authenticate"] == "Bearer"
    assert ponentes.ponentes == {}


@pytest.mark.parametrize("usuario", [ORGANIZADOR, ADMIN], ids=["organizador", "admin"])
def test_quien_tiene_el_permiso_crea_un_ponente_a_su_nombre(cliente, ponentes, auth, usuario):
    respuesta = cliente.post(
        "/speakers",
        json={"full_name": "  Ana Pérez  ", "bio": "Testing", "email": "Ana@Mail.com"},
        headers=auth(usuario),
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["full_name"] == "Ana Pérez"
    assert cuerpo["created_by"] == str(usuario.id)
    assert cuerpo["email"] == "Ana@mail.com"
    assert len(ponentes.ponentes) == 1


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        ({"full_name": "A"}, "full_name"),
        ({"full_name": "  A  "}, "full_name"),
        ({"full_name": "a" * 121}, "full_name"),
        ({"full_name": "Ana", "bio": "a" * 2001}, "bio"),
        ({"full_name": "Ana", "email": "no-es-un-correo"}, "email"),
        ({"full_name": "Ana", "created_by": str(ADMIN.id)}, "created_by"),
    ],
    ids=["nombre-1", "nombre-1-con-espacios", "nombre-121", "bio-2001", "email", "created_by"],
)
def test_un_ponente_invalido_responde_422_en_su_campo(cliente, ponentes, auth, cuerpo, campo):
    respuesta = cliente.post("/speakers", json=cuerpo, headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 422
    assert [e["field"] for e in respuesta.json()["errors"]] == [campo]
    assert ponentes.ponentes == {}


def test_buscar_pasa_q_y_la_pagina_al_repositorio(cliente, ponentes, auth):
    ponentes.crear(ponente())

    respuesta = cliente.get(
        "/speakers", params={"q": "an", "page": 2, "page_size": 5}, headers=auth(ORGANIZADOR)
    )

    assert respuesta.status_code == 200
    assert ponentes.busquedas == [{"q": "an", "offset": 5, "limite": 5}]
    assert (respuesta.json()["total"], respuesta.json()["page"]) == (1, 2)


# --- Editar y eliminar: el creador o el admin ----------------------------------------------


def editar(cliente, id_ponente, cuerpo: dict, headers: dict):
    return cliente.patch(f"/speakers/{id_ponente}", json=cuerpo, headers=headers)


def test_otro_organizador_no_edita_un_ponente_ajeno(cliente, ponentes, auth):
    ajeno = ponentes.crear(ponente(ORGANIZADOR))

    respuesta = editar(cliente, ajeno.id, {"full_name": "Otro"}, auth(OTRO_ORGANIZADOR))

    assert respuesta.status_code == 403
    assert ponentes.ponentes[ajeno.id].full_name == "Ana Pérez"


@pytest.mark.parametrize("usuario", [ORGANIZADOR, ADMIN], ids=["creador", "admin"])
def test_el_creador_y_el_admin_editan_un_ponente(cliente, ponentes, auth, usuario):
    existente = ponentes.crear(ponente(ORGANIZADOR))

    respuesta = editar(cliente, existente.id, {"full_name": "Ana María"}, auth(usuario))

    assert respuesta.status_code == 200
    assert respuesta.json()["full_name"] == "Ana María"
    assert respuesta.json()["bio"] == "Testing"
    assert ponentes.ponentes[existente.id].full_name == "Ana María"


def test_editar_valida_el_nombre_y_no_acepta_null(cliente, ponentes, auth):
    existente = ponentes.crear(ponente())

    corto = editar(cliente, existente.id, {"full_name": "A"}, auth(ORGANIZADOR))
    nulo = editar(cliente, existente.id, {"full_name": None}, auth(ORGANIZADOR))

    assert (corto.status_code, nulo.status_code) == (422, 422)
    assert ponentes.ponentes[existente.id].full_name == "Ana Pérez"


def test_un_asistente_no_edita_ni_elimina(cliente, ponentes, auth):
    existente = ponentes.crear(ponente())

    edicion = editar(cliente, existente.id, {"full_name": "Otro"}, auth(ASISTENTE))
    borrado = cliente.delete(f"/speakers/{existente.id}", headers=auth(ASISTENTE))

    assert (edicion.status_code, borrado.status_code) == (403, 403)
    assert existente.id in ponentes.ponentes


def test_un_ponente_que_no_existe_responde_404(cliente, ponentes, auth):
    edicion = editar(cliente, uuid4(), {"full_name": "Otro"}, auth(ADMIN))
    borrado = cliente.delete(f"/speakers/{uuid4()}", headers=auth(ADMIN))

    assert (edicion.status_code, borrado.status_code) == (404, 404)


def test_eliminar_un_ponente_sin_sesiones_responde_204(cliente, ponentes, auth):
    existente = ponentes.crear(ponente())

    respuesta = cliente.delete(f"/speakers/{existente.id}", headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 204
    assert ponentes.ponentes == {}


def test_eliminar_un_ponente_con_sesiones_responde_409(cliente, ponentes, auth):
    ocupado = ponente()
    ponentes.con_sesiones.add(ocupado.id)
    ponentes.crear(ocupado)

    respuesta = cliente.delete(f"/speakers/{ocupado.id}", headers=auth(ADMIN))

    assert respuesta.status_code == 409
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert ocupado.id in ponentes.ponentes


def test_otro_organizador_no_elimina_un_ponente_ajeno(cliente, ponentes, auth):
    ajeno = ponentes.crear(ponente(ORGANIZADOR))

    respuesta = cliente.delete(f"/speakers/{ajeno.id}", headers=auth(OTRO_ORGANIZADOR))

    assert respuesta.status_code == 403
    assert ajeno.id in ponentes.ponentes


# --- El email: solo para el creador y el admin ---------------------------------------------


@pytest.mark.parametrize(
    ("usuario", "lo_ve"),
    [(ORGANIZADOR, True), (ADMIN, True), (OTRO_ORGANIZADOR, False)],
    ids=["creador", "admin", "otro-organizador"],
)
def test_el_email_solo_sale_para_el_creador_y_el_admin(cliente, ponentes, auth, usuario, lo_ve):
    ponentes.crear(ponente(ORGANIZADOR))

    respuesta = cliente.get("/speakers", headers=auth(usuario))

    assert respuesta.status_code == 200
    [item] = respuesta.json()["items"]
    assert ("email" in item) is lo_ve
    if lo_ve:
        assert item["email"] == "ana@mail.com"
    # Lo demás sale igual para todos, aunque sea null.
    assert item["full_name"] == "Ana Pérez"
    assert "bio" in item


def test_un_ponente_sin_email_lo_muestra_como_null_a_quien_puede_verlo(cliente, ponentes, auth):
    ponentes.crear(ponente(ORGANIZADOR, email=None, bio=None))

    respuesta = cliente.get("/speakers", headers=auth(ORGANIZADOR))

    assert respuesta.status_code == 200
    [item] = respuesta.json()["items"]
    assert (item["email"], item["bio"]) == (None, None)
