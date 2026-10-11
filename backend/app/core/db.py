from collections.abc import Iterator

from sqlmodel import Session


def get_session() -> Iterator[Session]:
    """Una sesión por request. Punto de inyección: el engine y el commit/rollback se conectan
    junto con la configuración de la base; los tests unitarios la reemplazan por un doble."""
    raise RuntimeError("La sesión de base de datos todavía no está configurada")
    yield  # pragma: no cover
