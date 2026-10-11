from uuid import UUID

from sqlmodel import Session, select

from app.models.evento import Event


def escapar_like(texto: str) -> str:
    """Para ILIKE con ESCAPE '\\': `%`, `_` y la barra se buscan literalmente. La barra primero,
    si no se escaparían las barras que agrega el propio escape."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class RepositorioEventos:
    def __init__(self, session: Session) -> None:
        self.session = session

    def por_id(self, id_evento: UUID) -> Event | None:
        return self.session.get(Event, id_evento)

    def por_id_para_escribir(self, id_evento: UUID) -> Event | None:
        """Bloquea la fila hasta el fin de la transacción: dos cambios a la vez no se pisan."""
        consulta = select(Event).where(Event.id == id_evento).with_for_update()
        return self.session.exec(consulta).first()

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
