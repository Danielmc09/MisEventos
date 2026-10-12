"""Estado del servicio. Lanza excepciones de dominio; no sabe nada de HTTP."""

from typing import Protocol

from app.core.excepciones import ServiceUnavailable


class Salud(Protocol):
    def base_responde(self) -> bool: ...


def verificar(repo: Salud) -> None:
    if not repo.base_responde():
        raise ServiceUnavailable("La base de datos no responde.")
