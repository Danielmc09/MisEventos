import pytest
from pydantic import ValidationError

from app.core.config import Settings

# Valores de demostración de .env.example: válidos en desarrollo, prohibidos en producción.
DEMO_DB_URL = "postgresql+psycopg://miseventos:demo_local_db@db:5432/miseventos"
DEMO_JWT_SECRET = "demo-local-jwt-secret-solo-para-desarrollo-0001"
DEMO_ADMIN_PASSWORD = "Admin-Demo-2026"
DEMO_PASSWORD = "Demo-Local-2026"

DESARROLLO = {
    "ENV": "development",
    "DATABASE_URL": DEMO_DB_URL,
    "JWT_SECRET": DEMO_JWT_SECRET,
    "ACCESS_TOKEN_MINUTES": "15",
    "REFRESH_TOKEN_DAYS": "7",
    "CORS_ORIGINS": "http://localhost:5173",
    "SEED_DEMO": "true",
    "ADMIN_EMAIL": "admin@miseventos.local",
    "ADMIN_PASSWORD": DEMO_ADMIN_PASSWORD,
    "DEMO_PASSWORD": DEMO_PASSWORD,
    "LOG_LEVEL": "INFO",
}

PRODUCCION = {
    **DESARROLLO,
    "ENV": "production",
    "DATABASE_URL": "postgresql+psycopg://miseventos:Otra-Clave-Real-91@db:5432/miseventos",
    "JWT_SECRET": "x9Q2-secreto-real-de-produccion-con-mas-de-32",
    "SEED_DEMO": "false",
    "ADMIN_PASSWORD": "Admin-Real-Prod-2026!",
    "DEMO_PASSWORD": "Demo-Real-Prod-2026!",
}


@pytest.fixture
def entorno(monkeypatch):
    """Arma el entorno desde cero: sin .env ni variables heredadas de la máquina."""

    def armar(valores: dict[str, str]) -> Settings:
        for clave in DESARROLLO:
            monkeypatch.delenv(clave, raising=False)
        for clave, valor in valores.items():
            monkeypatch.setenv(clave, valor)
        return Settings(_env_file=None)

    return armar


def falla_nombrando(entorno, valores: dict[str, str], variable: str) -> None:
    with pytest.raises(ValidationError) as error:
        entorno(valores)
    # Solo ubicación y mensaje: str(error) incluye el input, que trae todos los nombres.
    explicacion = " ".join(f"{e['loc']} {e['msg']}" for e in error.value.errors())
    assert variable in explicacion


def test_desarrollo_con_los_valores_de_ejemplo_arranca(entorno):
    config = entorno(DESARROLLO)

    assert config.env == "development"
    assert config.cors_origins == ["http://localhost:5173"]
    assert config.seed_demo is True


def test_produccion_con_valores_propios_arranca(entorno):
    config = entorno(PRODUCCION)

    assert config.env == "production"


def test_cors_origins_se_separa_por_comas(entorno):
    config = entorno({**DESARROLLO, "CORS_ORIGINS": "http://a.test, http://b.test"})

    assert config.cors_origins == ["http://a.test", "http://b.test"]


def test_sin_cors_origins_no_se_permite_ningun_origen(entorno):
    valores = {k: v for k, v in DESARROLLO.items() if k != "CORS_ORIGINS"}

    assert entorno(valores).cors_origins == []


def test_sin_database_url_falla_nombrandola(entorno):
    valores = {k: v for k, v in DESARROLLO.items() if k != "DATABASE_URL"}

    falla_nombrando(entorno, valores, "DATABASE_URL")


def test_sin_jwt_secret_falla_nombrandolo(entorno):
    valores = {k: v for k, v in DESARROLLO.items() if k != "JWT_SECRET"}

    falla_nombrando(entorno, valores, "JWT_SECRET")


def test_jwt_secret_de_31_caracteres_falla_nombrandolo(entorno):
    falla_nombrando(entorno, {**DESARROLLO, "JWT_SECRET": "a" * 31}, "JWT_SECRET")


def test_jwt_secret_de_32_caracteres_alcanza(entorno):
    config = entorno({**DESARROLLO, "JWT_SECRET": "a" * 32})

    assert len(config.jwt_secret) == 32


@pytest.mark.parametrize("origenes", ["*", "http://localhost:5173,*", " * "])
def test_cors_origins_con_comodin_falla_nombrandola(entorno, origenes):
    falla_nombrando(entorno, {**DESARROLLO, "CORS_ORIGINS": origenes}, "CORS_ORIGINS")


@pytest.mark.parametrize(
    ("variable", "valor"),
    [
        ("ACCESS_TOKEN_MINUTES", "4"),
        ("ACCESS_TOKEN_MINUTES", "61"),
        ("REFRESH_TOKEN_DAYS", "0"),
        ("REFRESH_TOKEN_DAYS", "31"),
        ("ENV", "staging"),
    ],
)
def test_valores_fuera_de_rango_fallan_nombrando_la_variable(entorno, variable, valor):
    falla_nombrando(entorno, {**DESARROLLO, variable: valor}, variable)


@pytest.mark.parametrize(
    ("variable", "valor_de_demo"),
    [
        ("JWT_SECRET", DEMO_JWT_SECRET),
        ("ADMIN_PASSWORD", DEMO_ADMIN_PASSWORD),
        ("DEMO_PASSWORD", DEMO_PASSWORD),
        ("SEED_DEMO", "true"),
    ],
)
def test_produccion_rechaza_valores_de_demo(entorno, variable, valor_de_demo):
    falla_nombrando(entorno, {**PRODUCCION, variable: valor_de_demo}, variable)


def test_produccion_rechaza_la_contrasena_de_demo_de_la_base(entorno):
    otra_url_misma_clave = "postgresql+psycopg://otro_usuario:demo_local_db@prod-db:5432/eventos"

    falla_nombrando(entorno, {**PRODUCCION, "DATABASE_URL": otra_url_misma_clave}, "DATABASE_URL")
