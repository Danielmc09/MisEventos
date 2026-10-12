"""Mientras el usuario tiene una contraseña temporal, solo puede verse a sí mismo, cambiarla o
cerrar la sesión. Todo lo demás responde 403 `password-change-required`, aunque sea admin."""

import secrets
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.contrasenas import hashear
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.usuario import User
from tests.unit.dobles import RepositorioUsuariosFalso

TEMPORAL = secrets.token_urlsafe()
NUEVA = secrets.token_urlsafe()

# Lo único que puede hacer quien todavía tiene la contraseña temporal.
PERMITIDAS = {("GET", "/auth/me"), ("PATCH", "/auth/me/password"), ("POST", "/auth/logout")}
# Las que no leen el token: no saben quién llama, así que no tienen a quién frenar.
SIN_TOKEN = {
    ("GET", "/health"),
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("POST", "/auth/logout"),
}
TITULO = "Tenés que cambiar tu contraseña temporal para continuar"


@pytest.fixture
def admin() -> User:
    # Admin a propósito: con todos los permisos, el 403 solo puede venir del cambio pendiente.
    return User(
        email="nuevo.admin@mail.com",
        password_hash=hashear(TEMPORAL),
        role=Rol.ADMIN,
        must_change_password=True,
        created_at=datetime(2026, 10, 1, 12, tzinfo=UTC),
        updated_at=datetime(2026, 10, 1, 12, tzinfo=UTC),
    )


@pytest.fixture
def headers(con_repo, admin, settings) -> dict:
    con_repo(RepositorioUsuariosFalso(admin))
    token = crear_access_token(admin.id, settings.jwt_secret, 5)
    return {"Authorization": f"Bearer {token}"}


def rutas(app) -> list[tuple[str, str, bool]]:
    """Cada (método, ruta, si lee el token) registrada, según el OpenAPI de la app."""
    return [
        (metodo.upper(), ruta, "security" in operacion)
        for ruta, operaciones in app.openapi()["paths"].items()
        for metodo, operacion in operaciones.items()
    ]


def con_ids(ruta: str) -> str:
    """Completa los parámetros de la ruta con ids que no existen: el freno va antes de buscar."""
    partes = [str(uuid4()) if p.startswith("{") else p for p in ruta.split("/")]
    return "/".join(partes)


def test_con_la_temporal_solo_las_rutas_permitidas_no_responden_password_change_required(
    app, cliente, headers
):
    todas = rutas(app)
    assert todas, "No hay rutas para recorrer"

    sin_token = {(metodo, ruta) for metodo, ruta, lee_token in todas if not lee_token}
    assert sin_token == SIN_TOKEN

    pasan = set()
    for metodo, ruta, _ in todas:
        respuesta = cliente.request(metodo, con_ids(ruta), headers=headers, json={})
        frenada = (
            respuesta.status_code == 403
            and respuesta.json().get("type") == "password-change-required"
        )
        if frenada:
            assert respuesta.headers["content-type"] == "application/problem+json"
            assert respuesta.json()["title"] == TITULO
            assert respuesta.json()["trace_id"]
        else:
            pasan.add((metodo, ruta))

    assert pasan == PERMITIDAS | SIN_TOKEN


def test_con_la_temporal_ve_su_perfil_con_el_cambio_pendiente(cliente, headers):
    respuesta = cliente.get("/auth/me", headers=headers)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["must_change_password"] is True


def test_despues_de_cambiarla_navega_normal_con_el_token_nuevo(cliente, headers, admin):
    antes = cliente.get("/admin/users", headers=headers)
    assert antes.status_code == 403
    assert antes.json()["type"] == "password-change-required"

    cambio = cliente.patch(
        "/auth/me/password",
        json={"current_password": TEMPORAL, "new_password": NUEVA},
        headers=headers,
    )
    assert cambio.status_code == 200, cambio.text
    assert admin.must_change_password is False

    nuevo = {"Authorization": f"Bearer {cambio.json()['access_token']}"}
    despues = cliente.get("/admin/users", headers=nuevo)
    assert despues.status_code == 200, despues.text
    # El token de antes también: lo que frena es el estado del usuario, no el token.
    assert cliente.get("/admin/users", headers=headers).status_code == 200


def test_un_endpoint_publico_con_el_token_de_la_temporal_tambien_se_frena(cliente, headers):
    """El catálogo es público, pero quien manda el token se identifica: con el cambio pendiente,
    se frena igual que en el resto. Sin token sigue siendo público."""
    respuesta = cliente.get("/events", headers=headers)

    assert respuesta.status_code == 403
    assert respuesta.json()["type"] == "password-change-required"
