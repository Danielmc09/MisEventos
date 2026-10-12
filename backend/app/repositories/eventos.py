from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import EstadoInscripcion, Registration
from app.models.reserva import EstadoReserva, SessionRegistration
from app.models.sesion import Session as Sesion
from app.schemas.eventos import Cuando, FiltrosEventos, OrdenEventos

ORDEN = {
    OrdenEventos.START_AT: col(Event.start_at).asc(),
    OrdenEventos.START_AT_DESC: col(Event.start_at).desc(),
    OrdenEventos.NAME: col(Event.name).asc(),
}


def escapar_like(texto: str) -> str:
    """Para ILIKE con ESCAPE '\\': `%`, `_` y la barra se buscan literalmente. La barra primero,
    si no se escaparían las barras que agrega el propio escape."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class RepositorioEventos:
    def __init__(self, session: Session) -> None:
        self.session = session

    def buscar(
        self,
        filtros: FiltrosEventos,
        *,
        ver_todo: bool,
        borradores_de: UUID | None,
        offset: int,
        limite: int,
    ) -> tuple[list[Event], int]:
        """Una página y el total. Todo valor del usuario viaja como parámetro ligado."""
        condiciones: list[ColumnElement[bool]] = []
        if not ver_todo:
            visibles = col(Event.status) != EstadoEvento.DRAFT
            if borradores_de is not None:
                visibles = or_(visibles, col(Event.organizer_id) == borradores_de)
            condiciones.append(visibles)
        if filtros.q:
            patron = f"%{escapar_like(filtros.q)}%"
            condiciones.append(col(Event.name).ilike(patron, escape="\\"))
        if filtros.estados:
            condiciones.append(col(Event.status).in_(filtros.estados))
        if filtros.desde is not None:
            condiciones.append(col(Event.start_at) >= filtros.desde)
        if filtros.hasta is not None:
            condiciones.append(col(Event.start_at) <= filtros.hasta)
        ahora = datetime.now(UTC)
        if filtros.cuando == Cuando.PAST:
            condiciones.append(col(Event.end_at) < ahora)
        else:
            condiciones.append(col(Event.end_at) >= ahora)

        total = self.session.exec(select(func.count()).select_from(Event).where(*condiciones)).one()
        consulta = (
            select(Event)
            .where(*condiciones)
            .order_by(ORDEN[filtros.orden], col(Event.id))  # el id desempata: páginas estables
            .offset(offset)
            .limit(limite)
        )
        return list(self.session.exec(consulta).all()), total

    def por_id(self, id_evento: UUID) -> Event | None:
        return self.session.get(Event, id_evento)

    def por_nombre_y_organizador(self, nombre: str, organizer_id: UUID) -> Event | None:
        consulta = select(Event).where(Event.name == nombre, Event.organizer_id == organizer_id)
        return self.session.exec(consulta).first()

    def por_id_para_escribir(self, id_evento: UUID) -> Event | None:
        """Bloquea la fila hasta el fin de la transacción: dos cambios a la vez no se pisan."""
        consulta = select(Event).where(Event.id == id_evento).with_for_update()
        return self.session.exec(consulta).first()

    def inscritos(self, ids_evento: list[UUID]) -> dict[UUID, int]:
        """Las inscripciones activas de cada evento, en una sola consulta para todos."""
        por_evento = dict.fromkeys(ids_evento, 0)
        if not ids_evento:
            return por_evento
        consulta = (
            select(Registration.event_id, func.count())
            .where(
                col(Registration.event_id).in_(ids_evento),
                Registration.status == EstadoInscripcion.ACTIVE,
            )
            .group_by(col(Registration.event_id))
        )
        for id_evento, cantidad in self.session.exec(consulta).all():
            por_evento[id_evento] = cantidad
        return por_evento

    def inscrito(self, id_usuario: UUID, id_evento: UUID) -> bool:
        """Si el usuario tiene una inscripción activa en el evento."""
        consulta = select(Registration.id).where(
            Registration.user_id == id_usuario,
            Registration.event_id == id_evento,
            Registration.status == EstadoInscripcion.ACTIVE,
        )
        return self.session.exec(consulta).first() is not None

    def max_reservas_sin_capacidad(self, id_evento: UUID) -> int:
        """La mayor cantidad de reservas activas de una sesión del evento sin capacidad propia
        (las que usan la del evento); 0 si no hay. Una sola consulta agregada."""
        por_sesion = (
            select(func.count().label("activas"))
            .select_from(SessionRegistration)
            .join(Sesion, col(Sesion.id) == col(SessionRegistration.session_id))
            .where(
                Sesion.event_id == id_evento,
                col(Sesion.capacity).is_(None),
                SessionRegistration.status == EstadoReserva.ACTIVE,
            )
            .group_by(col(SessionRegistration.session_id))
            .subquery()
        )
        consulta = select(func.coalesce(func.max(por_sesion.c.activas), 0))
        return self.session.exec(consulta).one()

    def sesiones_de(self, id_evento: UUID) -> list[Sesion]:
        consulta = (
            select(Sesion)
            .where(Sesion.event_id == id_evento)
            .order_by(col(Sesion.start_at), col(Sesion.id))
        )
        return list(self.session.exec(consulta).all())

    def guardar(self, evento: Event) -> Event:
        self.session.add(evento)
        self.session.flush()
        self.session.refresh(evento)  # updated_at lo pone el trigger
        return evento

    def eliminar(self, evento: Event) -> None:
        self.session.delete(evento)
        self.session.flush()

    def crear(self, evento: Event) -> Event:
        self.session.add(evento)
        self.session.flush()
        self.session.refresh(evento)  # trae created_at y updated_at, que pone la base
        return evento
