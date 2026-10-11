from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session


def base_responde(session: Session) -> bool:
    try:
        session.exec(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
