"""Dobles de los repositorios: los tests unitarios no tocan la base."""

from datetime import UTC, datetime
from uuid import UUID

from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import EstadoInscripcion, Registration
from app.models.ponente import Speaker
from app.models.reserva import EstadoReserva, SessionRegistration
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
        self.inscripciones: dict[UUID, Registration] = {}
        # Qué filas se bloquearon y en qué orden. Se puede compartir con otro doble.
        self.bloqueos: list[UUID] = []
        # Con qué ids se contó cada vez: el listado cuenta toda la página en una sola llamada.
        self.conteos: list[list[UUID]] = []

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

    def inscritos(self, ids_evento: list[UUID]) -> dict[UUID, int]:
        self.conteos.append(list(ids_evento))
        activas = [i for i in self.inscripciones.values() if i.status == EstadoInscripcion.ACTIVE]
        return {id_: sum(1 for i in activas if i.event_id == id_) for id_ in ids_evento}

    def inscrito(self, id_usuario: UUID, id_evento: UUID) -> bool:
        return any(
            i.user_id == id_usuario
            and i.event_id == id_evento
            and i.status == EstadoInscripcion.ACTIVE
            for i in self.inscripciones.values()
        )

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

    def choques_de_ponentes(
        self, ids_ponente: list[UUID], inicio: datetime, fin: datetime, excluir: UUID | None
    ) -> list[tuple[Speaker, Sesion, Event]]:
        """La primera sesión que choca de cada ponente, en orden de id del ponente (como la base:
        el orden de presentación no es cosa del repositorio)."""
        self.consultas_de_choque.append(
            {"ids_ponente": list(ids_ponente), "inicio": inicio, "fin": fin, "excluir": excluir}
        )
        primeras: dict[UUID, tuple[Speaker, Sesion, Event]] = {}
        for sesion in sorted(self.eventos.sesiones.values(), key=lambda s: s.start_at):
            evento = self.eventos.eventos[sesion.event_id]
            if (
                sesion.id == excluir
                or evento.status == EstadoEvento.CANCELLED
                or not (sesion.start_at < fin and sesion.end_at > inicio)
            ):
                continue
            for id_ponente in self.vinculos.get(sesion.id, []):
                if id_ponente in ids_ponente and id_ponente not in primeras:
                    primeras[id_ponente] = (self.ponentes.ponentes[id_ponente], sesion, evento)
        return [primeras[id_] for id_ in sorted(primeras)]

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


class RepositorioInscripcionesFalso:
    """Guarda las inscripciones en el doble de eventos, que es el que las cuenta. Los datos de
    cada inscrito salen del doble de usuarios."""

    def __init__(
        self, eventos: RepositorioEventosFalso, usuarios: RepositorioUsuariosFalso | None = None
    ) -> None:
        self.eventos = eventos
        self.usuarios = usuarios or RepositorioUsuariosFalso()
        # Con qué se pidieron las inscripciones de un usuario; el filtro real lo hace la base.
        self.consultas_del_usuario: list[dict] = []

    def del_usuario(
        self, id_usuario: UUID, estado: EstadoInscripcion, cuando, offset: int, limite: int
    ) -> tuple[list[tuple[Registration, Event]], int]:
        self.consultas_del_usuario.append(
            {"id_usuario": id_usuario, "estado": estado, "cuando": cuando}
        )
        ahora = datetime.now(UTC)
        filas = [
            (i, self.eventos.eventos[i.event_id])
            for i in self.eventos.inscripciones.values()
            if i.user_id == id_usuario
            and i.status == estado
            and (self.eventos.eventos[i.event_id].end_at < ahora) == (cuando == "past")
        ]
        return filas[offset : offset + limite], len(filas)

    def del_evento(
        self, id_evento: UUID, offset: int, limite: int
    ) -> tuple[list[tuple[Registration, User]], int]:
        filas = [
            (i, self.usuarios.usuarios[i.user_id])
            for i in sorted(self.eventos.inscripciones.values(), key=lambda i: i.created_at)
            if i.event_id == id_evento
        ]
        return filas[offset : offset + limite], len(filas)

    def por_estado(self, id_evento: UUID) -> dict[EstadoInscripcion, int]:
        del_evento = [i for i in self.eventos.inscripciones.values() if i.event_id == id_evento]
        return {e: sum(1 for i in del_evento if i.status == e) for e in EstadoInscripcion}

    def alguna_de(self, id_usuario: UUID, id_evento: UUID) -> Registration | None:
        return next(
            (
                i
                for i in self.eventos.inscripciones.values()
                if i.user_id == id_usuario and i.event_id == id_evento
            ),
            None,
        )

    def activa_de(self, id_usuario: UUID, id_evento: UUID) -> Registration | None:
        return next(
            (
                i
                for i in self.eventos.inscripciones.values()
                if i.user_id == id_usuario
                and i.event_id == id_evento
                and i.status == EstadoInscripcion.ACTIVE
            ),
            None,
        )

    def activa_para_escribir(self, id_usuario: UUID, id_evento: UUID) -> Registration | None:
        """Como en la base: bloquea solo si la encuentra."""
        activa = self.activa_de(id_usuario, id_evento)
        if activa is not None:
            self.eventos.bloqueos.append(activa.id)
        return activa

    def crear(self, inscripcion: Registration) -> Registration:
        inscripcion.created_at = datetime.now(UTC)
        return self.guardar(inscripcion)

    def guardar(self, inscripcion: Registration) -> Registration:
        inscripcion.updated_at = datetime.now(UTC)
        self.eventos.inscripciones[inscripcion.id] = inscripcion
        return inscripcion


class RepositorioReservasFalso:
    """Las reservas en memoria. A qué evento pertenece cada una sale de las sesiones del doble de
    eventos."""

    def __init__(self, eventos: RepositorioEventosFalso) -> None:
        self.eventos = eventos
        self.reservas: dict[UUID, SessionRegistration] = {}

    def _activas(self) -> list[SessionRegistration]:
        return [r for r in self.reservas.values() if r.status == EstadoReserva.ACTIVE]

    def activa_de(self, id_usuario: UUID, id_sesion: UUID) -> SessionRegistration | None:
        return next(
            (r for r in self._activas() if r.user_id == id_usuario and r.session_id == id_sesion),
            None,
        )

    def activas_en(self, id_sesion: UUID) -> int:
        return sum(1 for r in self._activas() if r.session_id == id_sesion)

    def cruces(
        self, id_usuario: UUID, id_evento: UUID, inicio: datetime, fin: datetime
    ) -> list[Sesion]:
        """Las sesiones del evento con reserva activa del usuario que se cruzan con
        `[inicio, fin)`, por hora de inicio."""
        reservadas = {r.session_id for r in self._activas() if r.user_id == id_usuario}
        return [
            s
            for s in self.eventos.sesiones_de(id_evento)
            if s.id in reservadas and s.start_at < fin and inicio < s.end_at
        ]

    def cancelar_del_evento(self, id_usuario: UUID, id_evento: UUID, cuando: datetime) -> None:
        del_evento = {s.id for s in self.eventos.sesiones_de(id_evento)}
        for reserva in self._activas():
            if reserva.user_id == id_usuario and reserva.session_id in del_evento:
                reserva.status = EstadoReserva.CANCELLED
                reserva.cancelled_at = cuando

    def crear(self, reserva: SessionRegistration) -> SessionRegistration:
        reserva.created_at = datetime.now(UTC)
        return self.guardar(reserva)

    def guardar(self, reserva: SessionRegistration) -> SessionRegistration:
        reserva.updated_at = datetime.now(UTC)
        self.reservas[reserva.id] = reserva
        return reserva
