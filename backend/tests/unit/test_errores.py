import logging
from typing import Literal

import pytest
from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from app.api.errores import respuestas_de_error
from app.core.excepciones import Conflict, NotFound
from app.schemas.comunes import FechaUTC
from tests.unit.conftest import ORIGEN_PERMITIDO

PROBLEM_JSON = "application/problem+json"
SECRETO = "SELECT password_hash FROM users -- detalle interno"


class Alta(BaseModel):
    nombre: str
    cupo: int


@pytest.fixture
def rutas(app):
    @app.get("/conflicto")
    def conflicto() -> None:
        raise Conflict(
            "El evento alcanzó su capacidad de 50 personas.",
            tipo="capacity-full",
            titulo="El evento no tiene cupos",
        )

    @app.get("/no-existe", responses=respuestas_de_error(404, 409))
    def no_existe() -> None:
        raise NotFound()

    @app.post("/alta")
    def alta(datos: Alta) -> Alta:
        return datos

    @app.get("/explota")
    def explota() -> None:
        raise RuntimeError(SECRETO)

    return app


def problema(respuesta, status: int) -> dict:
    assert respuesta.status_code == status
    assert respuesta.headers["content-type"] == PROBLEM_JSON
    cuerpo = respuesta.json()
    assert cuerpo["status"] == status
    assert cuerpo["trace_id"] == respuesta.headers["X-Request-ID"]
    return cuerpo


def test_conflict_responde_409_problem_json(rutas, cliente):
    cuerpo = problema(cliente.get("/conflicto"), 409)

    assert cuerpo["type"] == "capacity-full"
    assert cuerpo["title"] == "El evento no tiene cupos"
    assert cuerpo["detail"] == "El evento alcanzó su capacidad de 50 personas."


def test_cada_excepcion_de_dominio_trae_su_tipo_y_titulo_por_defecto(rutas, cliente):
    cuerpo = problema(cliente.get("/no-existe"), 404)

    assert cuerpo["type"] == "not-found"
    assert cuerpo["title"] == "No encontramos lo que buscás"


def test_una_ruta_inexistente_tambien_es_problem_json(rutas, cliente):
    cuerpo = problema(cliente.get("/no-hay-nada-aca"), 404)

    assert cuerpo["type"] == "not-found"


def test_un_cuerpo_invalido_responde_422_con_errores_por_campo(rutas, cliente):
    cuerpo = problema(cliente.post("/alta", json={"cupo": "muchos"}), 422)

    assert cuerpo["type"] == "validation-error"
    campos = {error["field"] for error in cuerpo["errors"]}
    assert campos == {"nombre", "cupo"}
    assert all(error["message"] for error in cuerpo["errors"])
    assert "detail" not in cuerpo or not isinstance(cuerpo["detail"], list)


def test_un_error_no_esperado_responde_500_sin_filtrar_detalles(rutas, cliente, caplog):
    caplog.set_level(logging.INFO, logger="miseventos")

    respuesta = cliente.get("/explota")

    cuerpo = problema(respuesta, 500)
    assert cuerpo["type"] == "internal-error"
    texto = respuesta.text
    assert "password_hash" not in texto
    assert "RuntimeError" not in texto
    assert ".py" not in texto
    assert "Traceback" not in texto

    # El detalle completo queda en el log, con el mismo trace_id.
    errores = [r for r in caplog.records if r.exc_info]
    assert len(errores) == 1
    assert errores[0].campos["trace_id"] == cuerpo["trace_id"]
    assert SECRETO in str(errores[0].exc_info[1])


def test_el_500_lleva_cors_para_que_el_navegador_pueda_leerlo(rutas, cliente):
    respuesta = cliente.get("/explota", headers={"Origin": ORIGEN_PERMITIDO})

    cuerpo = problema(respuesta, 500)
    assert respuesta.headers.get("access-control-allow-origin") == ORIGEN_PERMITIDO
    assert respuesta.headers.get("X-Request-ID") == cuerpo["trace_id"]


def test_un_404_de_dominio_tambien_lleva_cors(rutas, cliente):
    respuesta = cliente.get("/no-existe", headers={"Origin": ORIGEN_PERMITIDO})

    problema(respuesta, 404)
    assert respuesta.headers.get("access-control-allow-origin") == ORIGEN_PERMITIDO


def test_respuestas_de_error_declara_problem_json_en_el_openapi(rutas, cliente):
    esquema = cliente.get("/openapi.json").json()

    respuestas = esquema["paths"]["/no-existe"]["get"]["responses"]
    assert set(respuestas) >= {"404", "409"}
    contenido = respuestas["409"]["content"][PROBLEM_JSON]["schema"]
    assert contenido["$ref"].endswith("/Problema")


class Formulario(BaseModel):
    nombre: str = Field(min_length=3)
    cupo: int = Field(default=1, ge=1, le=500)
    inicio: FechaUTC | None = None
    modalidad: Literal["presencial", "virtual"] = "presencial"
    codigo: str = "ok"
    fin: str = "ok"

    @field_validator("codigo")
    @classmethod
    def codigo_raro(cls, valor: str) -> str:
        if valor == "raro":
            raise PydanticCustomError("tipo_que_nadie_tradujo", "Some english text {x}", {"x": 1})
        if valor == "sin-ctx":
            # Un type traducido que llega sin el ctx que su mensaje necesita.
            raise PydanticCustomError("string_too_short", "Too short")
        return valor

    @field_validator("fin")
    @classmethod
    def fin_propio(cls, valor: str) -> str:
        if valor == "antes":
            raise ValueError("Debe ser posterior a start_at")
        return valor


@pytest.fixture
def formulario(app):
    @app.post("/formulario")
    def recibir(datos: Formulario) -> None:
        return None

    return app


def mensajes(cliente, cuerpo: dict) -> dict[str, str]:
    respuesta = cliente.post("/formulario", json=cuerpo)
    assert respuesta.status_code == 422
    return {e["field"]: e["message"] for e in respuesta.json()["errors"]}


@pytest.mark.parametrize(
    ("cuerpo", "campo", "mensaje"),
    [
        (
            {"nombre": "Feria", "inicio": "2026-10-13T10:00:00"},
            "inicio",
            "Debe incluir la zona horaria",
        ),
        ({}, "nombre", "Este campo es obligatorio"),
        ({"nombre": "ab"}, "nombre", "Debe tener al menos 3 caracteres"),
        ({"nombre": "Feria", "cupo": 0}, "cupo", "Debe ser mayor o igual que 1"),
        ({"nombre": "Feria", "cupo": 501}, "cupo", "Debe ser menor o igual que 500"),
        ({"nombre": "Feria", "cupo": "x"}, "cupo", "Debe ser un número entero"),
        (
            {"nombre": "Feria", "modalidad": "otra"},
            "modalidad",
            "Debe ser uno de: 'presencial' o 'virtual'",
        ),
        ({"nombre": "Feria", "codigo": "raro"}, "codigo", "Valor inválido"),
        ({"nombre": "Feria", "codigo": "sin-ctx"}, "codigo", "Valor inválido"),
        ({"nombre": "Feria", "fin": "antes"}, "fin", "Debe ser posterior a start_at"),
    ],
)
def test_los_mensajes_del_422_salen_en_espanol(formulario, cliente, cuerpo, campo, mensaje):
    assert mensajes(cliente, cuerpo)[campo] == mensaje


def test_ningun_mensaje_del_422_sale_en_ingles(formulario, cliente):
    respuesta = cliente.post(
        "/formulario", json={"nombre": "", "cupo": "x", "inicio": "ayer", "codigo": "raro"}
    )

    texto = respuesta.text
    for ingles in ("Input should", "Field required", "String should", "english"):
        assert ingles not in texto
