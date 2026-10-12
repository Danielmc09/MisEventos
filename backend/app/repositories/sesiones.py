from uuid import UUID

from sqlmodel import Session, col, delete, select

from app.models.evento import Event
from app.models.ponente import Speaker
from app.models.sesion import Session as Sesion
from app.models.sesion import SessionSpeaker


class RepositorioSesiones:
    def __init__(self, session: Session) -> None:
        self.session = session

    def por_id(self, id_sesion: UUID) -> Sesion | None:
        return self.session.get(Sesion, id_sesion)

    def por_id_para_escribir(self, id_sesion: UUID) -> Sesion | None:
        """Bloquea la fila y la relee: lo leído antes del bloqueo pudo haber cambiado."""
        consulta = (
            select(Sesion)
            .where(Sesion.id == id_sesion)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.session.exec(consulta).first()

    def ponentes_de(self, ids_sesion: list[UUID]) -> dict[UUID, list[Speaker]]:
        """Los ponentes de cada sesión, por nombre. Una sola consulta para todas."""
        por_sesion: dict[UUID, list[Speaker]] = {id_: [] for id_ in ids_sesion}
        if not ids_sesion:
            return por_sesion
        consulta = (
            select(SessionSpeaker.session_id, Speaker)
            .join(Speaker, col(Speaker.id) == col(SessionSpeaker.speaker_id))
            .where(col(SessionSpeaker.session_id).in_(ids_sesion))
            .order_by(col(Speaker.full_name), col(Speaker.id))
        )
        for id_sesion, ponente in self.session.exec(consulta).all():
            por_sesion[id_sesion].append(ponente)
        return por_sesion

    def sesiones_de_ponentes(self, ids_ponente: list[UUID]) -> list[tuple[Speaker, Sesion, Event]]:
        """Todas las sesiones de esos ponentes, en cualquier evento, con su evento."""
        if not ids_ponente:
            return []
        consulta = (
            select(Speaker, Sesion, Event)
            .join(SessionSpeaker, col(SessionSpeaker.speaker_id) == col(Speaker.id))
            .join(Sesion, col(Sesion.id) == col(SessionSpeaker.session_id))
            .join(Event, col(Event.id) == col(Sesion.event_id))
            .where(col(Speaker.id).in_(ids_ponente))
            .order_by(col(Sesion.start_at))
        )
        return [tuple(fila) for fila in self.session.exec(consulta).all()]

    def crear(self, sesion: Sesion, ids_ponente: list[UUID]) -> Sesion:
        return self.guardar(sesion, ids_ponente)

    def guardar(self, sesion: Sesion, ids_ponente: list[UUID] | None) -> Sesion:
        """Con `ids_ponente`, reemplaza los ponentes; con None, no los toca."""
        self.session.add(sesion)
        self.session.flush()
        if ids_ponente is not None:
            self.session.exec(
                delete(SessionSpeaker).where(col(SessionSpeaker.session_id) == sesion.id)
            )
            self.session.add_all(
                SessionSpeaker(session_id=sesion.id, speaker_id=id_) for id_ in ids_ponente
            )
            self.session.flush()
        self.session.refresh(sesion)  # created_at y updated_at los pone la base
        return sesion

    def eliminar(self, sesion: Sesion) -> None:
        self.session.delete(sesion)  # los vínculos se van en cascada, en la base
        self.session.flush()
