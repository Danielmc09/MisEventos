from sqlmodel import Session


class RepositorioInscripciones:
    def __init__(self, session: Session) -> None:
        self.session = session
