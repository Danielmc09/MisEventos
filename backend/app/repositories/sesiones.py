from sqlmodel import Session


class RepositorioSesiones:
    def __init__(self, session: Session) -> None:
        self.session = session
