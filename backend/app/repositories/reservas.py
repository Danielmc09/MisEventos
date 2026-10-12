from datetime import datetime
from uuid import UUID

from sqlalchemy import false
from sqlmodel import Session, col, func, select, update

from app.models.reserva import EstadoReserva, SessionRegistration
from app.models.sesion import Session as Sesion


class RepositorioReservas:
    def __init__(self, session: Session) -> None:
        self.session = session

    def activa_de(self, id_usuario: UUID, id_sesion: UUID) -> SessionRegistration | None:
        consulta = select(SessionRegistration).where(
            SessionRegistration.user_id == id_usuario,
            SessionRegistration.session_id == id_sesion,
            SessionRegistration.status == EstadoReserva.ACTIVE,
        )
        return self.session.exec(consulta).first()

    def activas_en(self, id_sesion: UUID) -> int:
        """Los lugares ocupados de la sesión: sus reservas activas."""
        consulta = (
            select(func.count())
            .select_from(SessionRegistration)
            .where(
                SessionRegistration.session_id == id_sesion,
                SessionRegistration.status == EstadoReserva.ACTIVE,
            )
        )
        return self.session.exec(consulta).one()

    def ocupacion(
        self, ids_sesion: list[UUID], id_usuario: UUID | None
    ) -> dict[UUID, tuple[int, bool]]:
        """Por sesión: (reservas activas, si una de ellas es del usuario). Una sola consulta
        agregada para todas; sin usuario (anónimo), ninguna es suya."""
        por_sesion = dict.fromkeys(ids_sesion, (0, False))
        if not ids_sesion:
            return por_sesion
        propia = false() if id_usuario is None else col(SessionRegistration.user_id) == id_usuario
        consulta = (
            select(SessionRegistration.session_id, func.count(), func.bool_or(propia))
            .where(
                col(SessionRegistration.session_id).in_(ids_sesion),
                SessionRegistration.status == EstadoReserva.ACTIVE,
            )
            .group_by(col(SessionRegistration.session_id))
        )
        for id_sesion, cantidad, es_propia in self.session.exec(consulta).all():
            por_sesion[id_sesion] = (cantidad, bool(es_propia))
        return por_sesion

    def reservadas_por_evento(
        self, id_usuario: UUID, ids_evento: list[UUID]
    ) -> dict[UUID, list[Sesion]]:
        """Por evento: las sesiones con reserva activa del usuario, por hora de inicio. Una sola
        consulta para todos los eventos."""
        por_evento: dict[UUID, list[Sesion]] = {id_: [] for id_ in ids_evento}
        if not ids_evento:
            return por_evento
        consulta = (
            select(Sesion)
            .join(SessionRegistration, col(SessionRegistration.session_id) == col(Sesion.id))
            .where(
                SessionRegistration.user_id == id_usuario,
                SessionRegistration.status == EstadoReserva.ACTIVE,
                col(Sesion.event_id).in_(ids_evento),
            )
            .order_by(col(Sesion.start_at), col(Sesion.id))
        )
        for sesion in self.session.exec(consulta).all():
            por_evento[sesion.event_id].append(sesion)
        return por_evento

    def cruces(
        self, id_usuario: UUID, id_evento: UUID, inicio: datetime, fin: datetime
    ) -> list[Sesion]:
        """Las sesiones del evento con reserva activa del usuario que se cruzan con
        `[inicio, fin)`, por hora de inicio. Terminar cuando la otra empieza no es cruce."""
        consulta = (
            select(Sesion)
            .join(SessionRegistration, col(SessionRegistration.session_id) == col(Sesion.id))
            .where(
                SessionRegistration.user_id == id_usuario,
                SessionRegistration.status == EstadoReserva.ACTIVE,
                Sesion.event_id == id_evento,
                col(Sesion.start_at) < fin,
                col(Sesion.end_at) > inicio,
            )
            .order_by(col(Sesion.start_at), col(Sesion.id))
        )
        return list(self.session.exec(consulta).all())

    def cancelar_del_evento(self, id_usuario: UUID, id_evento: UUID, cuando: datetime) -> None:
        """Cancela, en una sola sentencia, las reservas activas del usuario en las sesiones del
        evento. Las de otros eventos no se tocan."""
        del_evento = select(Sesion.id).where(Sesion.event_id == id_evento)
        sentencia = (
            update(SessionRegistration)
            .where(
                col(SessionRegistration.user_id) == id_usuario,
                col(SessionRegistration.status) == EstadoReserva.ACTIVE,
                col(SessionRegistration.session_id).in_(del_evento),
            )
            .values(status=EstadoReserva.CANCELLED, cancelled_at=cuando)
            # Si alguna de esas reservas está cargada en la sesión, se actualiza con lo que
            # devuelve la base: el subselect no se puede evaluar en Python.
            .execution_options(synchronize_session="fetch")
        )
        self.session.exec(sentencia)

    def crear(self, reserva: SessionRegistration) -> SessionRegistration:
        return self.guardar(reserva)

    def guardar(self, reserva: SessionRegistration) -> SessionRegistration:
        self.session.add(reserva)
        self.session.flush()
        self.session.refresh(reserva)  # created_at y updated_at los pone la base
        return reserva
