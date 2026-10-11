import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from tests.integration.infraestructura import migrar, revertir

pytestmark = pytest.mark.integration


def insertar_usuario(conexion: Connection, email: str) -> None:
    # SQL directo, sin pasar por el modelo: la regla tiene que valer aunque el código no normalice.
    conexion.execute(
        text(
            "INSERT INTO users (email, password_hash, role)"
            " VALUES (:email, '$argon2id$x', 'ATTENDEE')"
        ),
        {"email": email},
    )


def existe_tabla_users(conexion: Connection) -> bool:
    return conexion.execute(text("SELECT to_regclass('public.users') IS NOT NULL")).scalar_one()


def test_un_update_directo_cambia_updated_at_y_no_created_at(conexion):
    insertar_usuario(conexion, "ana@mail.com")
    antes = conexion.execute(
        text("SELECT created_at, updated_at FROM users WHERE email = 'ana@mail.com'")
    ).one()

    conexion.execute(text("UPDATE users SET full_name = 'Ana' WHERE email = 'ana@mail.com'"))

    despues = conexion.execute(
        text("SELECT created_at, updated_at FROM users WHERE email = 'ana@mail.com'")
    ).one()
    assert despues.created_at == antes.created_at
    assert despues.updated_at > antes.updated_at


def test_la_base_rechaza_un_email_duplicado_sin_distinguir_mayusculas(conexion):
    insertar_usuario(conexion, "ana@mail.com")

    with pytest.raises(IntegrityError, match="uq_users_email"):
        insertar_usuario(conexion, "ANA@Mail.com")


def test_un_usuario_nuevo_queda_activo_sin_cambio_obligatorio(conexion):
    insertar_usuario(conexion, "ana@mail.com")

    fila = conexion.execute(
        text("SELECT is_active, must_change_password FROM users WHERE email = 'ana@mail.com'")
    ).one()
    assert fila.is_active is True
    assert fila.must_change_password is False


def test_el_downgrade_a_0001_borra_users_y_su_tipo(conexion):
    revertir(conexion, "0001")
    assert not existe_tabla_users(conexion)
    assert conexion.execute(text("SELECT to_regtype('user_role') IS NULL")).scalar_one()

    migrar(conexion, "head")
    assert existe_tabla_users(conexion)
