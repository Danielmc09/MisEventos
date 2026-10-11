"""Dobles de los repositorios: los tests unitarios no tocan la base."""

from datetime import UTC, datetime
from uuid import UUID

from app.models.evento import Event
from app.models.usuario import User


class RepositorioUsuariosFalso:
    def __init__(self, *usuarios: User, choca_al_crear: bool = False) -> None:
        self.usuarios = {u.id: u for u in usuarios}
        self.creados: list[User] = []
        # Simula a otro registro del mismo email que ganó la carrera contra el índice único.
        self.choca_al_crear = choca_al_crear

    def por_email(self, email: str) -> User | None:
        buscado = email.strip().lower()
        return next((u for u in self.usuarios.values() if u.email == buscado), None)

    def por_id(self, id_: UUID) -> User | None:
        return self.usuarios.get(id_)

    def crear(self, usuario: User) -> bool:
        if self.choca_al_crear:
            return False
        self.creados.append(usuario)
        self.usuarios[usuario.id] = usuario
        return True


class RepositorioEventosFalso:
    def __init__(self, *eventos: Event) -> None:
        self.eventos = {e.id: e for e in eventos}
        self.busquedas: list[dict] = []

    def buscar(
        self, filtros, *, ver_todo: bool, borradores_de: UUID | None, offset: int, limite: int
    ) -> tuple[list[Event], int]:
        """Registra con qué se buscó; el filtrado lo hace la base y se prueba en integración."""
        self.busquedas.append(
            {
                "filtros": filtros,
                "ver_todo": ver_todo,
                "borradores_de": borradores_de,
                "offset": offset,
                "limite": limite,
            }
        )
        todos = list(self.eventos.values())
        return todos[offset : offset + limite], len(todos)

    def por_id(self, id_: UUID) -> Event | None:
        return self.eventos.get(id_)

    def por_id_para_escribir(self, id_: UUID) -> Event | None:
        return self.eventos.get(id_)

    def guardar(self, evento: Event) -> Event:
        evento.updated_at = datetime.now(UTC)
        self.eventos[evento.id] = evento
        return evento

    def eliminar(self, evento: Event) -> None:
        del self.eventos[evento.id]

    def crear(self, evento: Event) -> Event:
        # Lo que en la base pone el server_default.
        evento.created_at = evento.updated_at = datetime.now(UTC)
        self.eventos[evento.id] = evento
        return evento
