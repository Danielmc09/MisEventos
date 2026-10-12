"""Dobles de los repositorios: los tests unitarios no tocan la base."""

from datetime import UTC, datetime
from uuid import UUID

from app.models.evento import EstadoEvento, Event
from app.models.ponente import Speaker
from app.models.sesion import Session as Sesion
from app.models.usuario import User


class RepositorioUsuariosFalso:
    def __init__(self, *usuarios: User, choca_al_crear: bool = False) -> None:
        self.usuarios = {u.id: u for u in usuarios}
        self.creados: list[User] = []
        # Simula a otro registro del mismo email que ganó la carrera contra el índice único.
        self.choca_al_crear = choca_al_crear

    def por_email(self, email: str) -> User | None:
        buscado = email.strip().lower()
        return next((u for u in self.usuarios.values() if u.email == buscado), None)

    def por_id(self, id_: UUID) -> User | None:
        return self.usuarios.get(id_)

    def crear(self, usuario: User) -> bool:
        if self.choca_al_crear:
            return False
        self.creados.append(usuario)
        self.usuarios[usuario.id] = usuario
        return True


class RepositorioEventosFalso:
    def __init__(self, *eventos: Event) -> None:
        self.eventos = {e.id: e for e in eventos}
        self.busquedas: list[dict] = []
        self.sesiones: dict[UUID, Sesion] = {}
        # Qué filas se bloquearon y en qué orden. Se puede compartir con otro doble.
        self.bloqueos: list[UUID] = []

    def buscar(
        self, filtros, *, ver_todo: bool, borradores_de: UUID | None, offset: int, limite: int
    ) -> tuple[list[Event], int]:
        """Registra con qué se buscó; el filtrado lo hace la base y se prueba en integración."""
        self.busquedas.append(
            {
                "filtros": filtros,
                "ver_todo": ver_todo,
                "borradores_de": borradores_de,
                "offset": offset,
                "limite": limite,
            }
        )
        todos = list(self.eventos.values())
        return todos[offset : offset + limite], len(todos)

    def por_id(self, id_: UUID) -> Event | None:
        return self.eventos.get(id_)

    def por_nombre_y_organizador(self, nombre: str, organizer_id: UUID) -> Event | None:
        return next(
            (
                e
                for e in self.eventos.values()
                if e.name == nombre and e.organizer_id == organizer_id
            ),
            None,
        )

    def por_id_para_escribir(self, id_: UUID) -> Event | None:
        self.bloqueos.append(id_)
        return self.eventos.get(id_)

    def sesiones_de(self, id_evento: UUID) -> list[Sesion]:
        propias = [s for s in self.sesiones.values() if s.event_id == id_evento]
        return sorted(propias, key=lambda s: s.start_at)

    def guardar(self, evento: Event) -> Event:
        evento.updated_at = datetime.now(UTC)
        self.eventos[evento.id] = evento
        return evento

    def eliminar(self, evento: Event) -> None:
        del self.eventos[evento.id]

    def crear(self, evento: Event) -> Event:
        # Lo que en la base pone el server_default.
        evento.created_at = evento.updated_at = datetime.now(UTC)
        self.eventos[evento.id] = evento
        return evento


class RepositorioPonentesFalso:
    def __init__(self, *ponentes: Speaker, con_sesiones: tuple[Speaker, ...] = ()) -> None:
        self.ponentes = {p.id: p for p in ponentes}
        self.con_sesiones = {p.id for p in con_sesiones}
        self.busquedas: list[dict] = []
        self.bloqueos: list[UUID] = []

    def buscar(self, q: str | None, offset: int, limite: int) -> tuple[list[Speaker], int]:
        """Registra con qué se buscó; el ILIKE lo hace la base y se prueba en integración."""
        self.busquedas.append({"q": q, "offset": offset, "limite": limite})
        todos = list(self.ponentes.values())
        return todos[offset : offset + limite], len(todos)

    def por_id_para_escribir(self, id_: UUID) -> Speaker | None:
        self.bloqueos.append(id_)
        return self.ponentes.get(id_)

    def tiene_sesiones(self, id_: UUID) -> bool:
        return id_ in self.con_sesiones

    def por_email_y_creador(self, email: str, creador: UUID) -> Speaker | None:
        buscado = email.strip().lower()
        return next(
            (
                p
                for p in self.ponentes.values()
                if (p.email or "").lower() == buscado and p.created_by == creador
            ),
            None,
        )

    def crear(self, ponente: Speaker) -> Speaker:
        ponente.created_at = ponente.updated_at = datetime.now(UTC)
        self.ponentes[ponente.id] = ponente
        return ponente

    def guardar(self, ponente: Speaker) -> Speaker:
        ponente.updated_at = datetime.now(UTC)
        self.ponentes[ponente.id] = ponente
        return ponente

    def eliminar(self, ponente: Speaker) -> None:
        del self.ponentes[ponente.id]


class RepositorioSesionesFalso:
    """Guarda las sesiones en el doble de eventos (que las lista) y lee los ponentes del suyo."""

    def __init__(
        self, eventos: RepositorioEventosFalso, ponentes: RepositorioPonentesFalso
    ) -> None:
        self.eventos = eventos
        self.ponentes = ponentes
        self.vinculos: dict[UUID, list[UUID]] = {}
        # Con qué se preguntó por los choques; el filtro real lo hace la base.
        self.consultas_de_choque: list[dict] = []

    def ponentes_de(self, ids_sesion: list[UUID]) -> dict[UUID, list[Speaker]]:
        return {
            id_: sorted(
                (self.ponentes.ponentes[p] for p in self.vinculos.get(id_, [])),
                key=lambda p: p.full_name,
            )
            for id_ in ids_sesion
        }

    def sesiones_de_ponentes(self, ids_ponente: list[UUID]) -> list[tuple[Speaker, Sesion, Event]]:
        encontradas = []
        for id_sesion, ids in self.vinculos.items():
            sesion = self.eventos.sesiones[id_sesion]
            evento = self.eventos.eventos[sesion.event_id]
            for id_ponente in ids:
                if id_ponente in ids_ponente:
                    encontradas.append((self.ponentes.ponentes[id_ponente], sesion, evento))
        return encontradas

    def choque_de_ponentes(
        self, ids_ponente: list[UUID], inicio: datetime, fin: datetime, excluir: UUID | None
    ) -> tuple[Speaker, Sesion] | None:
        self.consultas_de_choque.append(
            {"ids_ponente": list(ids_ponente), "inicio": inicio, "fin": fin, "excluir": excluir}
        )
        sesiones = sorted(self.eventos.sesiones.values(), key=lambda s: s.start_at)
        for sesion in sesiones:
            evento = self.eventos.eventos[sesion.event_id]
            if (
                sesion.id == excluir
                or evento.status == EstadoEvento.CANCELLED
                or not (sesion.start_at < fin and sesion.end_at > inicio)
            ):
                continue
            for id_ponente in self.vinculos.get(sesion.id, []):
                if id_ponente in ids_ponente:
                    return self.ponentes.ponentes[id_ponente], sesion
        return None

    def por_id(self, id_: UUID) -> Sesion | None:
        return self.eventos.sesiones.get(id_)

    def por_id_para_escribir(self, id_: UUID) -> Sesion | None:
        self.eventos.bloqueos.append(id_)
        return self.eventos.sesiones.get(id_)

    def crear(self, sesion: Sesion, ids_ponente: list[UUID]) -> Sesion:
        sesion.created_at = datetime.now(UTC)
        return self.guardar(sesion, ids_ponente)

    def guardar(self, sesion: Sesion, ids_ponente: list[UUID] | None) -> Sesion:
        sesion.updated_at = datetime.now(UTC)
        self.eventos.sesiones[sesion.id] = sesion
        if ids_ponente is not None:
            self.vinculos[sesion.id] = list(ids_ponente)
        return sesion

    def eliminar(self, sesion: Sesion) -> None:
        del self.eventos.sesiones[sesion.id]
        self.vinculos.pop(sesion.id, None)
