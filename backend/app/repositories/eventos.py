from sqlmodel import Session


class RepositorioEventos:
    def __init__(self, session: Session) -> None:
        self.session = session
