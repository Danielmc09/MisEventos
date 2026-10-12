"""El carácter nulo no entra por ningún lado: cuerpo JSON, formulario ni query. Postgres no lo
guarda en un text y el driver lo rechaza con un error que terminaría en 500; se corta antes,
con un 422 en el campo."""

import re
import secrets
from uuid import uuid4

import pytest

from app.api.dependencias import repositorio_eventos, repositorio_usuarios
from app.core.permisos import Rol
from app.core.tokens import crear_access_token
from app.models.usuario import User
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
