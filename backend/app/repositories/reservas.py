from sqlmodel import Session


class RepositorioReservas:
    def __init__(self, session: Session) -> None:
        self.session = session
