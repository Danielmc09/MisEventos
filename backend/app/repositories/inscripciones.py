from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, col, func, select

from app.models.evento import Event
from app.models.inscripcion import EstadoInscripcion, Registration
from app.schemas.eventos import Cuando


class RepositorioInscripciones:
    def __init__(self, session: Session) -> None:
        self.session = session

    def del_usuario(
        self, id_usuario: UUID, estado: EstadoInscripcion, cuando: Cuando, offset: int, limite: int
    ) -> tuple[list[tuple[Registration, Event]], int]:
        """Una página de las inscripciones del usuario, cada una con su evento, y el total.
        Próximas: las de eventos que no terminaron, del más cercano al más lejano. Pasadas: las
        de eventos que terminaron, del más reciente al más viejo."""
        ahora = datetime.now(UTC)
        condiciones = [
            Registration.user_id == id_usuario,
            Registration.status == estado,
            col(Event.end_at) < ahora if cuando == Cuando.PAST else col(Event.end_at) >= ahora,
        ]
        unidas = select(Registration, Event).join(Event, col(Event.id) == Registration.event_id)
        total = self.session.exec(
            select(func.count())
            .select_from(Registration)
            .join(Event, col(Event.id) == Registration.event_id)
            .where(*condiciones)
        ).one()
        orden = col(Event.start_at).desc() if cuando == Cuando.PAST else col(Event.start_at).asc()
        consulta = (
            unidas.where(*condiciones)
            .order_by(orden, col(Registration.id))  # el id desempata: páginas estables
            .offset(offset)
            .limit(limite)
        )
        return [(i, e) for i, e in self.session.exec(consulta).all()], total

    def activa_de(self, id_usuario: UUID, id_evento: UUID) -> Registration | None:
        consulta = select(Registration).where(
            Registration.user_id == id_usuario,
            Registration.event_id == id_evento,
            Registration.status == EstadoInscripcion.ACTIVE,
        )
        return self.session.exec(consulta).first()

    def crear(self, inscripcion: Registration) -> Registration:
        return self.guardar(inscripcion)

    def guardar(self, inscripcion: Registration) -> Registration:
        self.session.add(inscripcion)
        self.session.flush()
        self.session.refresh(inscripcion)  # created_at y updated_at los pone la base
        return inscripcion
