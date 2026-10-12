from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session


class RepositorioSalud:
    def __init__(self, session: Session) -> None:
        self.session = session

    def base_responde(self) -> bool:
        try:
            self.session.exec(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True
