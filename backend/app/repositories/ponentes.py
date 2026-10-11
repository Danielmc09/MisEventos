from uuid import UUID

from sqlmodel import Session, col, func, select

from app.models.ponente import Speaker
from app.models.sesion import SessionSpeaker
from app.repositories.eventos import escapar_like


class RepositorioPonentes:
    def __init__(self, session: Session) -> None:
        self.session = session

    def buscar(self, q: str | None, offset: int, limite: int) -> tuple[list[Speaker], int]:
        """Una página y el total. El texto viaja como parámetro ligado y escapado."""
        condiciones = []
        if q:
            condiciones.append(col(Speaker.full_name).ilike(f"%{escapar_like(q)}%", escape="\\"))
        total = self.session.exec(
            select(func.count()).select_from(Speaker).where(*condiciones)
        ).one()
        consulta = (
            select(Speaker)
            .where(*condiciones)
            .order_by(col(Speaker.full_name), col(Speaker.id))  # el id desempata: páginas estables
            .offset(offset)
            .limit(limite)
        )
        return list(self.session.exec(consulta).all()), total

    def por_id_para_escribir(self, id_ponente: UUID) -> Speaker | None:
        """Bloquea la fila: borrar el ponente no compite con asignarlo a una sesión."""
        consulta = select(Speaker).where(Speaker.id == id_ponente).with_for_update()
        return self.session.exec(consulta).first()

    def tiene_sesiones(self, id_ponente: UUID) -> bool:
        consulta = select(SessionSpeaker.session_id).where(SessionSpeaker.speaker_id == id_ponente)
        return self.session.exec(consulta.limit(1)).first() is not None

    def crear(self, ponente: Speaker) -> Speaker:
        return self.guardar(ponente)

    def guardar(self, ponente: Speaker) -> Speaker:
        self.session.add(ponente)
        self.session.flush()
        self.session.refresh(ponente)  # created_at y updated_at los pone la base
        return ponente

    def eliminar(self, ponente: Speaker) -> None:
        self.session.delete(ponente)
        self.session.flush()
