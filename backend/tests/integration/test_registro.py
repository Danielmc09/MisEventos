import secrets

import pytest
from sqlalchemy import text
from sqlmodel import Session

from app.core.permisos import Rol
from app.models.usuario import User
from app.repositories.usuarios import RepositorioUsuarios

pytestmark = pytest.mark.integration

MENSAJE = {"message": "Registro recibido. Iniciá sesión con tu correo y contraseña."}


def fila(conexion, email: str):
    return conexion.execute(
        text(
            "SELECT id, email, full_name, password_hash, role, is_active, updated_at"
            " FROM users WHERE lower(email) = :email"
        ),
        {"email": email},
    ).all()


def test_un_email_nuevo_crea_un_attendee_activo_con_hash_argon2id(cliente_db, conexion):
    contrasena = secrets.token_urlsafe()
    respuesta = cliente_db.post(
        "/auth/register",
        json={"email": "ana@mail.com", "password": contrasena, "full_name": "Ana"},
    )

    assert respuesta.status_code == 201
    assert respuesta.json() == MENSAJE
    [usuario] = fila(conexion, "ana@mail.com")
    assert usuario.role == "ATTENDEE"
    assert usuario.is_active is True
    assert usuario.full_name == "Ana"
    assert usuario.password_hash.startswith("$argon2id$")


def test_un_email_existente_responde_igual_y_no_cambia_al_usuario(cliente_db, conexion):
    contrasena = secrets.token_urlsafe()
    otra_contrasena = secrets.token_urlsafe()
    nuevo = cliente_db.post(
        "/auth/register",
        json={"email": "ana@mail.com", "password": contrasena, "full_name": "Ana"},
    )
    antes = fila(conexion, "ana@mail.com")
    assert len(antes) == 1

    existente = cliente_db.post(
        "/auth/register",
        json={"email": "Ana@Mail.com ", "password": otra_contrasena, "full_name": "Impostora"},
    )

    assert nuevo.status_code == existente.status_code == 201
    assert nuevo.json() == existente.json() == MENSAJE
    assert fila(conexion, "ana@mail.com") == antes


def test_el_repositorio_no_falla_si_el_email_choca_contra_el_indice_unico(conexion):
    """La carrera entre dos registros: el segundo INSERT choca y no se convierte en un 500."""
    conexion.execute(
        text(
            "INSERT INTO users (email, password_hash, role)"
            " VALUES ('ana@mail.com', '$argon2id$x', 'ATTENDEE')"
        )
    )
    session = Session(bind=conexion, join_transaction_mode="create_savepoint")
    repo = RepositorioUsuarios(session)

    creado = repo.crear(User(email="ANA@mail.com", password_hash="$argon2id$y", role=Rol.ATTENDEE))

    assert creado is False
    # La sesión sigue usable después del choque.
    assert repo.por_email("ana@mail.com") is not None
    assert len(fila(conexion, "ana@mail.com")) == 1
