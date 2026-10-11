import logging

import pytest
from pydantic import BaseModel

from app.api.errores import respuestas_de_error
from app.core.excepciones import Conflict, NotFound

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


def test_respuestas_de_error_declara_problem_json_en_el_openapi(rutas, cliente):
    esquema = cliente.get("/openapi.json").json()

    respuestas = esquema["paths"]["/no-existe"]["get"]["responses"]
    assert set(respuestas) >= {"404", "409"}
    contenido = respuestas["409"]["content"][PROBLEM_JSON]["schema"]
    assert contenido["$ref"].endswith("/Problema")
