"""Registro, login y usuario actual. Lanza excepciones de dominio; no sabe nada de HTTP."""

import secrets
from typing import Protocol
from uuid import UUID

from app.core.contrasenas import hashear, verificar
from app.core.excepciones import DatosInvalidos, Forbidden, Unauthorized
from app.core.permisos import Rol
from app.core.tokens import crear_access_token, leer_access_token
from app.models.usuario import User

# Más largo que esto no se registra, así que no puede ser una credencial válida.
LARGO_MAXIMO_EMAIL = 254
LARGO_MAXIMO_CONTRASENA = 128

# Con un email inexistente se verifica contra este hash, para tardar lo mismo que con uno real.
_HASH_FICTICIO = hashear(secrets.token_urlsafe(32))


class Usuarios(Protocol):
    def por_email(self, email: str) -> User | None: ...
    def por_id(self, id_usuario: UUID) -> User | None: ...
    def crear(self, usuario: User) -> bool: ...


def registrar(repo: Usuarios, email: str, password: str, full_name: str | None) -> None:
    """Crea un ATTENDEE. Si el email ya existe no hace nada, y quien llama responde lo mismo."""
    if repo.por_email(email) is not None:
        return
    usuario = User(
        email=email, password_hash=hashear(password), full_name=full_name, role=Rol.ATTENDEE
    )
    repo.crear(usuario)  # si chocó con otro registro del mismo email, la respuesta es la misma


def _credenciales_invalidas() -> Unauthorized:
    # El mismo error para email inexistente, contraseña incorrecta y usuario desactivado.
    return Unauthorized(
        tipo="invalid-credentials", titulo="El correo o la contraseña no son correctos"
    )


def autenticar(repo: Usuarios, email: str, password: str) -> User:
    # Se corta antes de Argon2, que procesaría cualquier tamaño: una contraseña de 1 MB por
    # request sería un DoS barato.
    if len(email) > LARGO_MAXIMO_EMAIL or len(password) > LARGO_MAXIMO_CONTRASENA:
        raise _credenciales_invalidas()
    usuario = repo.por_email(email)
    if usuario is None:
        verificar(_HASH_FICTICIO, password)
        raise _credenciales_invalidas()
    if not verificar(usuario.password_hash, password) or not usuario.is_active:
        raise _credenciales_invalidas()
    return usuario


def iniciar_sesion(repo: Usuarios, email: str, password: str, secreto: str, minutos: int) -> str:
    """El access token del usuario, si las credenciales son correctas."""
    return crear_access_token(autenticar(repo, email, password).id, secreto, minutos)


def usuario_del_token(repo: Usuarios, token: str, secreto: str) -> User:
    usuario = repo.por_id(leer_access_token(token, secreto))
    if usuario is None or not usuario.is_active:
        raise Unauthorized()
    return usuario


def exigir_contrasena_definitiva(usuario: User) -> None:
    """Con la contraseña temporal que le dio el admin, el usuario solo puede cambiarla: el admin
    la vio, así que todavía no es solo suya."""
    if usuario.must_change_password:
        raise Forbidden(
            tipo="password-change-required",
            titulo="Tenés que cambiar tu contraseña temporal para continuar",
        )


def cambiar_contrasena(usuario: User, actual: str, nueva: str, secreto: str, minutos: int) -> str:
    """Guarda la nueva contraseña y devuelve un access token nuevo. El cambio lo persiste la
    transacción del request, que ya tiene cargado al usuario."""
    if not verificar(usuario.password_hash, actual):
        raise DatosInvalidos("current_password", "La contraseña actual no es correcta")
    if nueva == actual:
        raise DatosInvalidos(
            "new_password", "La nueva contraseña tiene que ser distinta de la actual"
        )
    usuario.password_hash = hashear(nueva)
    usuario.must_change_password = False
    return crear_access_token(usuario.id, secreto, minutos)
