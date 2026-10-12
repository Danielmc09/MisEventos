"""La consulta de choques de ponentes, compilada para PostgreSQL sin tocar una base."""

import warnings
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.repositories.sesiones import RepositorioSesiones


class SesionQueGuardaLaConsulta:
    """Doble de la sesión de base: guarda la consulta que recibe y no devuelve filas."""

    def __init__(self) -> None:
        self.consultas: list[object] = []

    def exec(self, consulta: object) -> list[object]:
        self.consultas.append(consulta)
        return []


def test_los_choques_usan_distinct_on_por_ponente_sin_avisos_de_deprecacion():
    sesion = SesionQueGuardaLaConsulta()
    repo = RepositorioSesiones(sesion)  # type: ignore[arg-type]

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        filas = repo.choques_de_ponentes(
            [uuid4()],
            datetime(2026, 10, 1, 10, tzinfo=UTC),
            datetime(2026, 10, 1, 11, tzinfo=UTC),
            excluir=uuid4(),
        )
        (consulta,) = sesion.consultas
        sql = str(consulta.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]

    assert filas == []
    assert "SELECT DISTINCT ON (speakers.id)" in sql
    assert "ORDER BY speakers.id, sessions.start_at, sessions.id" in sql
