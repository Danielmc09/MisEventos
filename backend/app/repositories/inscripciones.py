from uuid import UUID

from sqlmodel import Session, select

from app.models.inscripcion import EstadoInscripcion, Registration


class RepositorioInscripciones:
    def __init__(self, session: Session) -> None:
        self.session = session

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
