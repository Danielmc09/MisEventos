import pytest

from app.core.config import Settings
from app.core.contrasenas import hashear, verificar
from app.core.permisos import Rol
from app.models.usuario import User
from app.scripts import seed
from app.scripts.seed import CredencialesDemo, credenciales_demo, sembrar_usuarios
from tests.unit.dobles import RepositorioUsuariosFalso

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


# --- Usuarios demo -------------------------------------------------------------------------

DEMO = CredencialesDemo(
    admin_email="Admin@MisEventos.local",
    admin_password="Admin-Test-2026",
    demo_password="Demo-Test-2026",
)


def test_crea_el_admin_y_los_dos_usuarios_demo_con_sus_roles():
    repo = RepositorioUsuariosFalso()

    sembrar_usuarios(repo, DEMO)

    assert len(repo.creados) == 3
    por_email = {u.email: u for u in repo.creados}
    assert {email: u.role for email, u in por_email.items()} == {
        "admin@miseventos.local": Rol.ADMIN,
        "organizador@miseventos.local": Rol.ORGANIZER,
        "asistente@miseventos.local": Rol.ATTENDEE,
    }
    assert all(u.is_active and not u.must_change_password for u in repo.creados)
    assert verificar(por_email["admin@miseventos.local"].password_hash, "Admin-Test-2026")
    assert verificar(por_email["organizador@miseventos.local"].password_hash, "Demo-Test-2026")
    assert verificar(por_email["asistente@miseventos.local"].password_hash, "Demo-Test-2026")


def test_no_toca_un_usuario_que_ya_existe_aunque_cambio_su_contrasena():
    hash_propio = hashear("Clave-Propia-1")
    admin = User(email="admin@miseventos.local", password_hash=hash_propio, role=Rol.ADMIN)
    asistente = User(
        email="asistente@miseventos.local",
        password_hash=hash_propio,
        role=Rol.ATTENDEE,
        full_name="Nombre que puso la persona",
    )
    repo = RepositorioUsuariosFalso(admin, asistente)

    sembrar_usuarios(repo, DEMO)

    assert [u.email for u in repo.creados] == ["organizador@miseventos.local"]
    assert admin.password_hash == asistente.password_hash == hash_propio
    assert asistente.full_name == "Nombre que puso la persona"
    assert len(repo.usuarios) == 3


def test_correrlo_dos_veces_no_crea_nada_la_segunda():
    repo = RepositorioUsuariosFalso()
    sembrar_usuarios(repo, DEMO)

    sembrar_usuarios(repo, DEMO)

    assert len(repo.creados) == 3
