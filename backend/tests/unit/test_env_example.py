"""El .env.example de la raíz tiene que coincidir con los valores de demo que la configuración
rechaza en producción. Si divergen, el bloqueo en producción deja pasar las credenciales
publicadas."""

from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

from app.core.config import VALORES_DE_DEMO, Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"
DE_POSTGRES = {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"}
DEL_FRONTEND = {"VITE_API_URL"}


@pytest.fixture(scope="module")
def ejemplo() -> dict[str, str | None]:
    return dotenv_values(ENV_EXAMPLE)


def test_trae_todas_las_variables_de_la_configuracion(ejemplo):
    esperadas = {campo.upper() for campo in Settings.model_fields} | DE_POSTGRES | DEL_FRONTEND

    assert esperadas - ejemplo.keys() == set()


@pytest.mark.parametrize("variable", ["JWT_SECRET", "ADMIN_PASSWORD", "DEMO_PASSWORD"])
def test_los_valores_de_demo_coinciden_con_los_que_bloquea_produccion(ejemplo, variable):
    assert ejemplo[variable] == VALORES_DE_DEMO[variable]


def test_la_contrasena_de_la_base_coincide_con_la_que_bloquea_produccion(ejemplo):
    assert make_url(ejemplo["DATABASE_URL"]).password == VALORES_DE_DEMO["DATABASE_URL"]


def test_postgres_se_crea_con_las_credenciales_de_database_url(ejemplo):
    url = make_url(ejemplo["DATABASE_URL"])

    assert (ejemplo["POSTGRES_USER"], ejemplo["POSTGRES_PASSWORD"], ejemplo["POSTGRES_DB"]) == (
        url.username,
        url.password,
        url.database,
    )


def test_con_los_valores_de_ejemplo_la_configuracion_arranca_en_desarrollo(ejemplo):
    config = Settings(_env_file=None, **{k: v for k, v in ejemplo.items() if v is not None})

    assert config.env == "development"
    assert config.seed_demo is True
