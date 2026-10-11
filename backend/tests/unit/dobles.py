"""Dobles de los repositorios: los tests unitarios no tocan la base."""

from uuid import UUID

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
