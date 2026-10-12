import pytest
from sqlalchemy.exc import OperationalError

from app.core.db import get_session
from tests.unit.conftest import ORIGEN_PERMITIDO


class SesionQueResponde:
    def __init__(self) -> None:
        self.consultas: list[str] = []

    def exec(self, sentencia):
        self.consultas.append(str(sentencia))


class SesionCaida:
    def exec(self, sentencia):
        raise OperationalError(str(sentencia), {}, ConnectionRefusedError("db:5432"))


@pytest.fixture
def con_base(app):
    def usar(sesion) -> None:
        app.dependency_overrides[get_session] = lambda: sesion

    return usar


def test_health_responde_200_si_la_base_responde_al_select_1(con_base, cliente):
    sesion = SesionQueResponde()
    con_base(sesion)

    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}
    assert sesion.consultas == ["SELECT 1"]


def test_health_responde_503_si_la_base_no_responde(con_base, cliente):
    con_base(SesionCaida())

    respuesta = cliente.get("/health")

    assert respuesta.status_code == 503
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo["type"] == "service-unavailable"
    assert "db:5432" not in respuesta.text


def test_un_origen_permitido_recibe_cors_sin_credenciales(con_base, cliente):
    # El token viaja en Authorization y el front no manda cookies: no hay credenciales
    # que habilitar entre orígenes.
    con_base(SesionQueResponde())

    simple = cliente.get("/health", headers={"Origin": ORIGEN_PERMITIDO})
    preflight = cliente.options(
        "/health",
        headers={
            "Origin": ORIGEN_PERMITIDO,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") == ORIGEN_PERMITIDO
    assert simple.headers.get("access-control-allow-origin") == ORIGEN_PERMITIDO
    assert "access-control-allow-credentials" not in preflight.headers
    assert "access-control-allow-credentials" not in simple.headers


def test_un_origen_fuera_de_cors_origins_no_recibe_allow_origin(con_base, cliente):
    con_base(SesionQueResponde())

    simple = cliente.get("/health", headers={"Origin": "http://atacante.test"})
    preflight = cliente.options(
        "/health",
        headers={"Origin": "http://atacante.test", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in simple.headers
    assert "access-control-allow-origin" not in preflight.headers


def test_swagger_documenta_la_api_y_el_503_de_health(cliente):
    esquema = cliente.get("/openapi.json").json()

    assert esquema["info"]["title"] == "Mis Eventos API"
    assert esquema["info"]["version"]
    assert esquema["info"]["description"]
    health = esquema["paths"]["/health"]["get"]
    assert health.get("description")
    assert "503" in health["responses"]
    assert cliente.get("/docs").status_code == 200
