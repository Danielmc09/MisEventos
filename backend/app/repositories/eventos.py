from uuid import UUID

from sqlmodel import Session

from app.models.evento import Event


class RepositorioEventos:
    def __init__(self, session: Session) -> None:
        self.session = session

    def por_id(self, id_evento: UUID) -> Event | None:
        return self.session.get(Event, id_evento)

    def crear(self, evento: Event) -> Event:
        self.session.add(evento)
        self.session.flush()
        self.session.refresh(evento)  # trae created_at y updated_at, que pone la base
        return evento
