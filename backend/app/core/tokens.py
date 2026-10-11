"""Access tokens: JWT HS256 firmado con JWT_SECRET. No lleva el rol: el usuario se lee de la
base en cada request, así un cambio de rol o una desactivación rigen de inmediato."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.excepciones import Unauthorized

ALGORITMO = "HS256"


def crear_access_token(id_usuario: UUID, secreto: str, minutos: int) -> str:
    ahora = datetime.now(UTC)
    claims = {"sub": str(id_usuario), "iat": ahora, "exp": ahora + timedelta(minutes=minutos)}
    return jwt.encode(claims, secreto, algorithm=ALGORITMO)


def leer_access_token(token: str, secreto: str) -> UUID:
    """El id del usuario del token. Firma inválida, vencido, `alg` distinto de HS256 (incluido
    `none`) o sin `sub`, `iat` o `exp` → Unauthorized."""
    try:
        claims = jwt.decode(
            token, secreto, algorithms=[ALGORITMO], options={"require": ["sub", "iat", "exp"]}
        )
        return UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError) as error:
        raise Unauthorized() from error
