"""Contra PostgreSQL real, que es donde el carácter nulo rompe: el driver lo rechaza en
cualquier parámetro de texto y, si nada lo frena antes, la respuesta es un 500. Cada campo de
texto de cada endpoint recibe el nulo con el resto del request válido, autenticado como admin
y apuntando a un evento que existe."""

import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.campos_de_texto import CampoDeTexto, campos_de_texto

pytestmark = pytest.mark.integration


def admin(cliente, conexion) -> tuple[str, str, str]:
    """Un admin nuevo: (email, contraseña, access token)."""
    email = f"admin-{uuid4().hex}@mail.com"
    clave = secrets.token_urlsafe(16)
    registro = cliente.post("/auth/register", json={"email": email, "password": clave})
    assert registro.status_code == 201
    conexion.execute(text("UPDATE users SET role = 'ADMIN' WHERE email = :e"), {"e": email})
    login = cliente.post("/auth/login", data={"username": email, "password": clave})
    assert login.status_code == 200
    return email, clave, login.json()["access_token"]


def cuerpo_de_evento() -> dict:
    inicio = datetime.now(UTC) + timedelta(days=30)
    return {
        "name": f"Evento {uuid4().hex[:8]}",
        "description": "Charlas de Python",
        "location": "Bogotá",
        "start_at": inicio.isoformat(),
        "end_at": (inicio + timedelta(hours=8)).isoformat(),
        "capacity": 100,
    }


def entrada_valida(campo: CampoDeTexto, email: str, clave: str) -> dict:
    """El request válido de cada esquema de entrada. Un esquema nuevo sin entrada acá hace
    fallar el test: hay que decir cómo se ve un request válido para que el nulo llegue lejos."""
    if campo.ubicacion == "query":
        return {}
    validos = {
        "RegistroEntrada": lambda: {
            "email": f"nuevo-{uuid4().hex}@mail.com",
            "password": secrets.token_urlsafe(16),
            "full_name": "Ana Pérez",
        },
        "Body_login_auth_login_post": lambda: {
            "grant_type": "password",
            "username": email,
            "password": clave,
        },
        "CambioContrasenaEntrada": lambda: {
            "current_password": clave,
            "new_password": secrets.token_urlsafe(16),
        },
        "EventoEntrada": cuerpo_de_evento,
        "EventoEdicion": lambda: {"name": f"Editado {uuid4().hex[:8]}"},
    }
    assert campo.esquema in validos, f"falta el request válido de {campo.esquema}"
    return validos[campo.esquema]()


def test_el_caracter_nulo_en_cualquier_campo_de_texto_nunca_da_500(cliente_db, conexion):
    _, _, token_dueno = admin(cliente_db, conexion)
    creado = cliente_db.post(
        "/events", json=cuerpo_de_evento(), headers={"Authorization": f"Bearer {token_dueno}"}
    )
    assert creado.status_code == 201
    parametros_de_ruta = {"id_evento": creado.json()["id"]}

    revisados: dict[str, list[str]] = {"body": [], "form": [], "query": []}
    fallas: list[str] = []
    for campo in campos_de_texto(cliente_db.app.openapi()):
        # Un admin por campo: si el nulo llegara a cambiarle la contraseña, no arrastra al resto.
        email, clave, token = admin(cliente_db, conexion)
        ruta = re.sub(r"\{([^}]+)\}", lambda m: parametros_de_ruta[m.group(1)], campo.ruta)
        datos = entrada_valida(campo, email, clave)
        datos[campo.nombre] = str(datos.get(campo.nombre, "texto")) + "\x00"
        argumentos = {"query": "params", "form": "data", "body": "json"}[campo.ubicacion]

        respuesta = cliente_db.request(
            campo.metodo.upper(),
            ruta,
            headers={"Authorization": f"Bearer {token}"},
            **{argumentos: datos},
        )

        revisados[campo.ubicacion].append(str(campo))
        if respuesta.status_code >= 500:
            fallas.append(f"{campo} → {respuesta.status_code}")

    assert all(revisados.values()), f"faltó recorrer algún tipo de campo: {revisados}"
    assert fallas == []
