"""El carácter nulo no entra por ningún lado: cuerpo JSON, formulario ni query. Postgres no lo
guarda en un text y el driver lo rechaza con un error que terminaría en 500; se corta antes,
con un 422 en el campo."""

import re
import secrets
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from app.api.dependencias import repositorio_eventos, repositorio_usuarios
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.usuario import User
from app.schemas.comunes import EntradaBase
from tests.campos_de_texto import CampoDeTexto, campos_de_texto
from tests.unit.dobles import RepositorioEventosFalso, RepositorioUsuariosFalso

MENSAJE = "No puede contener el carácter nulo"
ADMIN = User(email="admin@mail.com", password_hash="$argon2id$x", role=Rol.ADMIN)


@pytest.fixture
def token(app, settings) -> str:
    """Un admin, para que ningún endpoint corte con 401 o 403 antes de validar la entrada."""
    usuarios = RepositorioUsuariosFalso(ADMIN)
    app.dependency_overrides[repositorio_usuarios] = lambda: usuarios
    app.dependency_overrides[repositorio_eventos] = lambda: RepositorioEventosFalso()
    return crear_access_token(ADMIN.id, settings.jwt_secret, 5)


def enviar(cliente, campo: CampoDeTexto, valor: str, token: str):
    ruta = re.sub(r"\{[^}]+\}", str(uuid4()), campo.ruta)
    enviado = {campo.nombre: valor}
    argumentos = {
        "query": {"params": enviado},
        "form": {"data": enviado},
        "body": {"json": enviado},
    }[campo.ubicacion]
    return cliente.request(
        campo.metodo.upper(), ruta, headers={"Authorization": f"Bearer {token}"}, **argumentos
    )


def mensajes_de(respuesta, nombre: str) -> list[str]:
    errores = respuesta.json().get("errors") or []
    return [e["message"] for e in errores if e["field"].split(".")[0] == nombre]


def test_ningun_campo_de_texto_acepta_el_caracter_nulo(app, cliente, token):
    texto = secrets.token_urlsafe(12)
    revisados: dict[str, list[str]] = {"body": [], "form": [], "query": []}
    fallas: list[str] = []

    for campo in campos_de_texto(app.openapi()):
        if mensajes_de(enviar(cliente, campo, texto, token), campo.nombre):
            continue  # el campo no acepta texto libre (un email, un enum): ya responde 422
        revisados[campo.ubicacion].append(str(campo))

        respuesta = enviar(cliente, campo, texto + "\x00", token)

        if respuesta.status_code != 422 or MENSAJE not in mensajes_de(respuesta, campo.nombre):
            fallas.append(f"{campo} → {respuesta.status_code}")

    assert all(revisados.values()), f"faltó recorrer algún tipo de campo: {revisados}"
    assert fallas == []


@pytest.mark.parametrize(
    "tipo",
    ["APPLICATION/X-WWW-FORM-URLENCODED", "application/x-www-form-urlencoded; charset=utf-8"],
    ids=["en-mayusculas", "con-charset"],
)
@pytest.mark.usefixtures("token")  # los repositorios en memoria
def test_el_formulario_se_revisa_aunque_el_content_type_venga_escrito_distinto(cliente, tipo):
    clave = secrets.token_urlsafe(12)

    respuesta = cliente.post(
        "/auth/login",
        content=f"username=ana%40mail.com%00&password={clave}",
        headers={"Content-Type": tipo},
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["errors"] == [{"field": "username", "message": MENSAJE}]


@pytest.mark.parametrize(
    ("metodo", "ruta", "esperado"),
    [("POST", "/auth/logout", 204), ("GET", "/events", 200)],
    ids=["logout", "listado"],
)
@pytest.mark.usefixtures("token")  # los repositorios en memoria
def test_un_endpoint_sin_formulario_no_lee_el_cuerpo_aunque_el_content_type_lo_anuncie(
    cliente, metodo, ruta, esperado
):
    # Un multipart sin boundary no se puede parsear: si la revisión del nulo leyera el cuerpo
    # de un endpoint que no declara formulario, respondería 400.
    respuesta = cliente.request(metodo, ruta, headers={"Content-Type": "multipart/form-data"})

    assert respuesta.status_code == esperado


# --- El esquema base, sin HTTP --------------------------------------------------------------


class Sub(BaseModel):  # un submodelo cualquiera, que no hereda de la base
    nota: str


class ConAnidados(EntradaBase):
    etiquetas: list[str] = []
    extras: dict[str, str] = {}
    sub: Sub | None = None
    pares: list[tuple[str, int]] = []


@pytest.mark.parametrize(
    ("datos", "campo"),
    [
        ({"etiquetas": ["python", "py\x00con"]}, "etiquetas"),
        ({"extras": {"ciudad": "Bogo\x00tá"}}, "extras"),
        ({"extras": {"ciu\x00dad": "Bogotá"}}, "extras"),
        ({"sub": {"nota": "\x00"}}, "sub"),
        ({"pares": [["a\x00", 1]]}, "pares"),
    ],
    ids=["lista", "valor-de-dict", "clave-de-dict", "submodelo", "tupla-en-lista"],
)
def test_la_base_rechaza_el_nulo_tambien_en_textos_anidados(datos, campo):
    with pytest.raises(ValidationError) as error:
        ConAnidados.model_validate(datos)

    assert [(e["loc"][0], e["msg"]) for e in error.value.errors()] == [
        (campo, f"Value error, {MENSAJE}")
    ]


def test_la_base_deja_pasar_los_anidados_sin_nulo():
    datos = {
        "etiquetas": ["python"],
        "extras": {"ciudad": "Bogotá"},
        "sub": {"nota": "ok"},
        "pares": [["a", 1]],
    }

    assert ConAnidados.model_validate(datos).model_dump() == datos | {"pares": [("a", 1)]}
