from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.usuario import User

INDICE_EMAIL = "uq_users_email"


class RepositorioUsuarios:
    def __init__(self, session: Session) -> None:
        self.session = session

    def por_email(self, email: str) -> User | None:
        # lower(email) usa el índice único uq_users_email.
        consulta = select(User).where(func.lower(User.email) == email.strip().lower())
        return self.session.exec(consulta).first()

    def crear(self, usuario: User) -> bool:
        """False si el email ya existía: otro registro ganó la carrera contra el índice único."""
        try:
            with self.session.begin_nested():
                self.session.add(usuario)
        except IntegrityError as error:
            if INDICE_EMAIL not in str(error.orig):
                raise
            return False
        return True
