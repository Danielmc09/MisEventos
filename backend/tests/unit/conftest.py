import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

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
