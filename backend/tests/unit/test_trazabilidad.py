import json
import logging
import uuid

import pytest

from app.core.excepciones import NotFound
from app.core.logs import FormatoJson

TOKEN = "eyJ-token-secreto-que-no-va-al-log"


@pytest.fixture
def con_ruta(app):
    @app.get("/prueba")
    def prueba() -> dict[str, str]:
        return {"ok": "si"}

    return app


def es_uuid(valor: str) -> bool:
    try:
        uuid.UUID(valor)
    except (TypeError, ValueError):
        return False
    return True


def test_sin_x_request_id_la_respuesta_trae_un_uuid_generado(con_ruta, cliente):
    respuesta = cliente.get("/prueba")

    assert es_uuid(respuesta.headers.get("X-Request-ID"))


def test_con_un_uuid_se_devuelve_el_mismo(con_ruta, cliente):
    propio = str(uuid.uuid4())

    respuesta = cliente.get("/prueba", headers={"X-Request-ID": propio})

    assert respuesta.headers.get("X-Request-ID") == propio


@pytest.mark.parametrize(
    "formato",
    [
        "359DAD91-CEC1-4995-BEF0-7FB658100BC6",
        "e90f4f7b769b40dc991bc452a2523032",
        "{f06468e7-3bb0-480e-bcc9-8c15007d4b2a}",
    ],
)
def test_un_uuid_en_otro_formato_vuelve_exactamente_igual(app, cliente, caplog, formato):
    @app.get("/no-esta")
    def no_esta() -> None:
        raise NotFound()

    caplog.set_level(logging.INFO, logger="miseventos")

    respuesta = cliente.get("/no-esta", headers={"X-Request-ID": formato})

    assert respuesta.headers.get("X-Request-ID") == formato
    assert respuesta.json()["trace_id"] == formato
    assert [linea["trace_id"] for linea in lineas_de_acceso(caplog)] == [formato]


@pytest.mark.parametrize("invalido", ["no-es-un-uuid", "1234", "<script>", "a" * 200])
def test_con_un_x_request_id_que_no_es_uuid_se_genera_otro(con_ruta, cliente, invalido):
    respuesta = cliente.get("/prueba", headers={"X-Request-ID": invalido})

    devuelto = respuesta.headers.get("X-Request-ID")
    assert devuelto != invalido
    assert es_uuid(devuelto)


def lineas_de_acceso(caplog) -> list[dict]:
    registros = [r for r in caplog.records if r.name == "miseventos.acceso"]
    formato = FormatoJson()
    lineas = [formato.format(r) for r in registros]
    assert all(linea.startswith("{") for linea in lineas), lineas
    return [json.loads(linea) for linea in lineas]


def test_el_log_del_request_es_json_con_trace_id_y_sin_authorization(con_ruta, cliente, caplog):
    caplog.set_level(logging.INFO, logger="miseventos")

    respuesta = cliente.get(
        "/prueba?x=1",
        headers={"Authorization": f"Bearer {TOKEN}", "Cookie": f"refresh={TOKEN}"},
    )

    lineas = lineas_de_acceso(caplog)
    assert len(lineas) == 1
    linea = lineas[0]
    assert linea["trace_id"] == respuesta.headers["X-Request-ID"]
    assert linea["method"] == "GET"
    assert linea["path"] == "/prueba"
    assert linea["status"] == 200
    assert linea["level"] == "INFO"
    assert isinstance(linea["duration_ms"], int | float)
    assert linea["ts"].endswith("Z")
    texto = json.dumps(linea).lower()
    assert "authorization" not in texto
    assert TOKEN.lower() not in texto


@pytest.mark.parametrize("status", [401, 403])
def test_401_y_403_se_loguean_en_warning(app, cliente, caplog, status):
    from fastapi import Response

    @app.get("/denegado")
    def denegado() -> Response:
        return Response(status_code=status)

    caplog.set_level(logging.INFO, logger="miseventos")

    cliente.get("/denegado")

    assert [linea["level"] for linea in lineas_de_acceso(caplog)] == ["WARNING"]


def test_el_user_id_va_al_log_si_hay_sesion(app, cliente, caplog):
    from fastapi import Request

    @app.get("/con-sesion")
    def con_sesion(request: Request) -> dict[str, str]:
        request.state.user_id = "u-123"
        return {}

    caplog.set_level(logging.INFO, logger="miseventos")

    cliente.get("/con-sesion")

    assert [linea.get("user_id") for linea in lineas_de_acceso(caplog)] == ["u-123"]
