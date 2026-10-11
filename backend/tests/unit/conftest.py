import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencias import repositorio_usuarios
from app.core.config import Settings
from app.main import create_app
from tests.unit.dobles import RepositorioUsuariosFalso

ORIGEN_PERMITIDO = "http://localhost:5173"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        ENV="development",
        DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/test",
        JWT_SECRET="s" * 32,
        CORS_ORIGINS=ORIGEN_PERMITIDO,
        LOG_LEVEL="INFO",
    )


@pytest.fixture
def app(settings) -> FastAPI:
    """La app real. Los tests le montan sus propias rutas de prueba."""
    return create_app(settings)


@pytest.fixture
def cliente(app) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def con_repo(app):
    """Reemplaza el repositorio de usuarios de la app por un doble en memoria."""

    def usar(repo: RepositorioUsuariosFalso) -> RepositorioUsuariosFalso:
        app.dependency_overrides[repositorio_usuarios] = lambda: repo
        return repo

    return usar
