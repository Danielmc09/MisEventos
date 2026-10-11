from sqlmodel import Session

from app.models.usuario import User


class RepositorioUsuarios:
    def __init__(self, session: Session) -> None:
        self.session = session

    def por_email(self, email: str) -> User | None:
        return None

    def crear(self, usuario: User) -> bool:
        return True
