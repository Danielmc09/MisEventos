import pytest

from app.core.config import Settings
from app.scripts import seed
from app.scripts.seed import CredencialesDemo, credenciales_demo

CREDENCIALES = {
    "ADMIN_EMAIL": "admin@miseventos.local",
    "ADMIN_PASSWORD": "Admin-Demo-2026",
    "DEMO_PASSWORD": "Demo-Local-2026",
}
BASE = {
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/x",
    "JWT_SECRET": "s" * 32,
}


def settings(**valores: str) -> Settings:
    return Settings(_env_file=None, **BASE, **valores)


def test_con_las_tres_variables_devuelve_las_credenciales():
    assert credenciales_demo(settings(**CREDENCIALES)) == CredencialesDemo(
        admin_email="admin@miseventos.local",
        admin_password="Admin-Demo-2026",
        demo_password="Demo-Local-2026",
    )


@pytest.mark.parametrize("falta", sorted(CREDENCIALES))
def test_sin_una_variable_el_seed_falla_nombrandola(falta):
    valores = {k: v for k, v in CREDENCIALES.items() if k != falta}

    with pytest.raises(RuntimeError, match=falta):
        credenciales_demo(settings(**valores))


def test_un_valor_vacio_cuenta_como_faltante():
    with pytest.raises(RuntimeError, match="DEMO_PASSWORD"):
        credenciales_demo(settings(**{**CREDENCIALES, "DEMO_PASSWORD": ""}))


def test_si_faltan_varias_las_nombra_a_todas():
    with pytest.raises(RuntimeError) as error:
        credenciales_demo(settings(ADMIN_EMAIL="admin@miseventos.local"))

    assert "ADMIN_PASSWORD" in str(error.value)
    assert "DEMO_PASSWORD" in str(error.value)


class SesionDoble:
    def __init__(self) -> None:
        self.llamadas: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.llamadas.append("close")

    def commit(self):
        self.llamadas.append("commit")

    def rollback(self):
        self.llamadas.append("rollback")


@pytest.fixture
def entorno(monkeypatch):
    for clave in [*CREDENCIALES, *BASE, "SEED_DEMO", "ENV"]:
        monkeypatch.delenv(clave, raising=False)
    monkeypatch.chdir("/")  # sin .env alrededor

    def armar(**valores: str) -> None:
        for clave, valor in {**BASE, **valores}.items():
            monkeypatch.setenv(clave, valor)

    return armar


@pytest.fixture
def base_doble(monkeypatch):
    """Reemplaza la conexión real; registra qué sesiones se pidieron y qué se sembró."""
    registro = {"sesiones": [], "sembrado": []}

    def fabrica(url):
        def nueva():
            sesion = SesionDoble()
            registro["sesiones"].append(sesion)
            return sesion

        return nueva

    monkeypatch.setattr(seed, "crear_fabrica_de_sesiones", fabrica, raising=False)
    monkeypatch.setattr(seed, "sembrar", lambda s, c: registro["sembrado"].append(c))
    return registro


def test_main_siembra_en_una_transaccion_y_la_confirma(entorno, base_doble):
    entorno(**CREDENCIALES)

    seed.main([])

    assert [c.admin_email for c in base_doble["sembrado"]] == ["admin@miseventos.local"]
    assert [s.llamadas for s in base_doble["sesiones"]] == [["commit", "close"]]


def test_main_sin_credenciales_termina_con_un_mensaje_que_nombra_la_variable(entorno, base_doble):
    entorno(ADMIN_EMAIL="admin@miseventos.local", ADMIN_PASSWORD="x")

    with pytest.raises(SystemExit) as salida:
        seed.main([])

    assert "DEMO_PASSWORD" in str(salida.value.code)
    assert base_doble["sesiones"] == []


def test_al_arrancar_sin_seed_demo_no_hace_nada_ni_pide_credenciales(entorno, base_doble):
    entorno(SEED_DEMO="false")

    seed.main(["--solo-si-seed-demo"])

    assert base_doble["sesiones"] == []


def test_al_arrancar_con_seed_demo_siembra(entorno, base_doble):
    entorno(SEED_DEMO="true", **CREDENCIALES)

    seed.main(["--solo-si-seed-demo"])

    assert len(base_doble["sembrado"]) == 1
