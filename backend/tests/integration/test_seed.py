import pytest
from sqlalchemy import text
from sqlmodel import Session

from app.scripts.seed import CredencialesDemo, sembrar

pytestmark = pytest.mark.integration

DEMO = CredencialesDemo(
    admin_email="admin@miseventos.local",
    admin_password="Admin-Test-2026",
    demo_password="Demo-Test-2026",
)
ROLES = {
    "admin@miseventos.local": "ADMIN",
    "organizador@miseventos.local": "ORGANIZER",
    "asistente@miseventos.local": "ATTENDEE",
}
CONTRASENAS = {
    "admin@miseventos.local": "Admin-Test-2026",
    "organizador@miseventos.local": "Demo-Test-2026",
    "asistente@miseventos.local": "Demo-Test-2026",
}


def correr_seed(conexion) -> None:
    """Como el script: una transacción con commit, que acá queda en un savepoint del test."""
    with Session(bind=conexion, join_transaction_mode="create_savepoint") as session:
        sembrar(session, DEMO)
        session.commit()


def usuarios_demo(conexion) -> list[tuple[str, str]]:
    return conexion.execute(
        text("SELECT lower(email), role FROM users WHERE lower(email) = ANY(:emails)"),
        {"emails": list(ROLES)},
    ).all()


def login(cliente, email: str, password: str):
    return cliente.post("/auth/login", data={"username": email, "password": password})


def test_correr_el_seed_dos_veces_deja_exactamente_los_tres_usuarios_demo(conexion):
    correr_seed(conexion)
    correr_seed(conexion)

    filas = usuarios_demo(conexion)
    assert len(filas) == 3
    assert {email: str(rol) for email, rol in filas} == ROLES


def test_los_usuarios_demo_hacen_login_sin_cambio_obligatorio(cliente_db, conexion):
    correr_seed(conexion)

    for email, password in CONTRASENAS.items():
        respuesta = login(cliente_db, email, password)
        assert respuesta.status_code == 200, email
        token = respuesta.json()["access_token"]
        perfil = cliente_db.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert perfil.status_code == 200, email
        assert perfil.json()["role"] == ROLES[email]
        assert perfil.json()["must_change_password"] is False
        assert perfil.json()["is_active"] is True


def test_cada_usuario_demo_ve_su_nombre_en_el_perfil(cliente_db, conexion):
    correr_seed(conexion)

    nombres = {}
    for email, password in CONTRASENAS.items():
        token = login(cliente_db, email, password).json()["access_token"]
        perfil = cliente_db.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        nombres[email] = perfil.json()["full_name"]

    assert nombres == {
        "admin@miseventos.local": "Ana Administradora",
        "organizador@miseventos.local": "Oscar Organizador",
        "asistente@miseventos.local": "Andrea Asistente",
    }


def test_completa_el_nombre_del_demo_que_existe_sin_nombre_y_respeta_el_que_tiene(conexion):
    # SQL directo: usuarios demo de antes de que el seed les pusiera nombre.
    for email, rol, nombre in [
        ("admin@miseventos.local", "ADMIN", None),
        ("organizador@miseventos.local", "ORGANIZER", "Otro Nombre"),
    ]:
        conexion.execute(
            text(
                "INSERT INTO users (email, password_hash, role, full_name)"
                " VALUES (:email, '$argon2id$x', :rol, :nombre)"
            ),
            {"email": email, "rol": rol, "nombre": nombre},
        )

    correr_seed(conexion)

    filas = conexion.execute(
        text(
            "SELECT lower(email), full_name, password_hash FROM users"
            " WHERE lower(email) = ANY(:emails)"
        ),
        {"emails": list(ROLES)},
    ).all()
    por_email = {email: (nombre, hash_) for email, nombre, hash_ in filas}
    assert por_email["admin@miseventos.local"] == ("Ana Administradora", "$argon2id$x")
    assert por_email["organizador@miseventos.local"] == ("Otro Nombre", "$argon2id$x")
    assert por_email["asistente@miseventos.local"][0] == "Andrea Asistente"


def test_el_seed_no_restaura_la_contrasena_que_un_usuario_demo_cambio(cliente_db, conexion):
    correr_seed(conexion)
    email, vieja, nueva = "asistente@miseventos.local", "Demo-Test-2026", "Clave-Propia-77"
    primer_login = login(cliente_db, email, vieja)
    assert primer_login.status_code == 200
    token = primer_login.json()["access_token"]
    cambio = cliente_db.patch(
        "/auth/me/password",
        json={"current_password": vieja, "new_password": nueva},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cambio.status_code == 200

    correr_seed(conexion)

    assert login(cliente_db, email, nueva).status_code == 200
    assert login(cliente_db, email, vieja).status_code == 401
    assert len(usuarios_demo(conexion)) == 3
