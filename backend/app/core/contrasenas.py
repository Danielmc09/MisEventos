"""Contraseñas con Argon2id. Nunca un hash rápido: una contraseña se puede adivinar probando."""

import secrets
import string

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher(type=Type.ID)

LARGO_TEMPORAL = 16
ALFABETO_TEMPORAL = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")


def hashear(contrasena: str) -> str:
    return _hasher.hash(contrasena)


def verificar(hash_guardado: str, contrasena: str) -> bool:
    try:
        return _hasher.verify(hash_guardado, contrasena)
    except (VerificationError, InvalidHashError):
        return False


def generar_contrasena_temporal() -> str:
    """La que el sistema le da a un usuario creado o restablecido por el admin. Aleatoria
    (`secrets`), de letras y dígitos sin los que se confunden al dictarla o copiarla: 16 de 57
    símbolos son unos 93 bits, más de lo que hace falta para una contraseña de un solo uso."""
    return "".join(secrets.choice(ALFABETO_TEMPORAL) for _ in range(LARGO_TEMPORAL))
