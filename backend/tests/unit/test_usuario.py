from app.core.permisos import Rol
from app.models.usuario import User


def nuevo(email: str) -> User:
    return User(email=email, password_hash="$argon2id$x", role=Rol.ATTENDEE)


def test_el_email_se_guarda_en_minusculas_y_sin_espacios():
    assert nuevo("  Ana@Mail.com ").email == "ana@mail.com"


def test_el_email_se_normaliza_tambien_al_cambiarlo():
    usuario = nuevo("ana@mail.com")

    usuario.email = " Otra@Mail.COM"

    assert usuario.email == "otra@mail.com"


def test_un_usuario_nuevo_esta_activo_y_sin_cambio_obligatorio_de_contrasena():
    usuario = nuevo("ana@mail.com")

    assert usuario.is_active is True
    assert usuario.must_change_password is False


def test_el_email_es_varchar_254_y_el_hash_no_tiene_limite():
    columnas = User.__table__.c

    assert columnas.email.type.length == 254
    assert columnas.password_hash.type.length is None
