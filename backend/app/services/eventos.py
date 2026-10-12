"""Eventos: quién los crea, quién los ve y con qué reglas.

Lanza excepciones de dominio; no sabe nada de HTTP."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.core.excepciones import (
    Conflict,
    DatosInvalidos,
    Forbidden,
    NotFound,
    TransicionInvalida,
)
from app.core.permisos import Permiso, tiene_permiso
from app.models.evento import EstadoEvento, Event
from app.models.sesion import Session as Sesion
from app.models.usuario import User
from app.schemas.eventos import EventoEdicion, EventoEntrada, FiltrosEventos


class Eventos(Protocol):
    def por_id(self, id_evento: UUID) -> Event | None: ...
    def crear(self, evento: Event) -> Event: ...
    def por_id_para_escribir(self, id_evento: UUID) -> Event | None: ...
    def sesiones_de(self, id_evento: UUID) -> list[Sesion]: ...
    def inscritos(self, ids_evento: list[UUID]) -> dict[UUID, int]: ...
    def inscrito(self, id_usuario: UUID, id_evento: UUID) -> bool: ...
    def max_reservas_sin_capacidad(self, id_evento: UUID) -> int: ...
    def guardar(self, evento: Event) -> Event: ...
    def eliminar(self, evento: Event) -> None: ...
    def buscar(
        self,
        filtros: FiltrosEventos,
        *,
        ver_todo: bool,
        borradores_de: UUID | None,
        offset: int,
        limite: int,
    ) -> tuple[list[Event], int]: ...


@dataclass(frozen=True)
class ConInscritos:
    """Un evento con sus inscripciones activas y, en el detalle, si quien pregunta es una."""

    evento: Event
    inscritos: int
    inscrito: bool = False


def _con_inscritos(repo: Eventos, evento: Event) -> ConInscritos:
    return ConInscritos(evento, repo.inscritos([evento.id])[evento.id])


def puede_ver(usuario: User | None, evento: Event) -> bool:
    """Publicados y cancelados, todos. Un borrador, su dueño (si puede crear eventos) y el admin."""
    if evento.status != EstadoEvento.DRAFT:
        return True
    if usuario is None:
        return False
    if tiene_permiso(usuario, Permiso.EVENTO_GESTIONAR_TODOS):
        return True
    return tiene_permiso(usuario, Permiso.EVENTO_CREAR) and evento.organizer_id == usuario.id


def listar(
    repo: Eventos, usuario: User | None, filtros: FiltrosEventos, offset: int, limite: int
) -> tuple[list[ConInscritos], int]:
    """Una página de lo que el usuario puede ver, con el total. Es la misma regla de `puede_ver`,
    pero la aplica la base: pedir `status=DRAFT` no muestra borradores que no le tocan. Los
    inscritos de toda la página salen de una sola consulta, no de una por evento."""
    ver_todo = usuario is not None and tiene_permiso(usuario, Permiso.EVENTO_GESTIONAR_TODOS)
    borradores_de = None
    if usuario is not None and not ver_todo and tiene_permiso(usuario, Permiso.EVENTO_CREAR):
        borradores_de = usuario.id
    eventos, total = repo.buscar(
        filtros, ver_todo=ver_todo, borradores_de=borradores_de, offset=offset, limite=limite
    )
    inscritos = repo.inscritos([e.id for e in eventos])
    return [ConInscritos(e, inscritos[e.id]) for e in eventos], total


def obtener(repo: Eventos, usuario: User | None, id_evento: UUID) -> Event:
    """El evento, o NotFound si no existe o si no lo puede ver: no se revela que existe."""
    evento = repo.por_id(id_evento)
    if evento is None or not puede_ver(usuario, evento):
        raise NotFound()
    return evento


def detalle(repo: Eventos, usuario: User | None, id_evento: UUID) -> ConInscritos:
    """El evento, con sus inscripciones activas y si el usuario tiene una. Anónimo: no."""
    evento = obtener(repo, usuario, id_evento)
    inscrito = usuario is not None and repo.inscrito(usuario.id, evento.id)
    return ConInscritos(evento, repo.inscritos([evento.id])[evento.id], inscrito)


def crear(repo: Eventos, usuario: User, datos: EventoEntrada) -> Event:
    """Un borrador a nombre de quien lo crea."""
    if not tiene_permiso(usuario, Permiso.EVENTO_CREAR):
        raise Forbidden()
    if datos.start_at <= datetime.now(UTC):
        raise DatosInvalidos("start_at", "Tiene que estar en el futuro")
    return repo.crear(Event(**datos.model_dump(), organizer_id=usuario.id))


def ya_empezo(evento: Event) -> bool:
    return evento.start_at <= datetime.now(UTC)


def finalizado(evento: Event) -> bool:
    return evento.end_at < datetime.now(UTC)


def _exigir_gestion(usuario: User, evento: Event | None) -> Event:
    """Primero la visibilidad (lo que no ve es 404, no se revela que existe) y después el
    permiso: el dueño que puede crear eventos, o el admin."""
    if evento is None or not puede_ver(usuario, evento):
        raise NotFound()
    es_dueno = tiene_permiso(usuario, Permiso.EVENTO_CREAR) and evento.organizer_id == usuario.id
    if not (es_dueno or tiene_permiso(usuario, Permiso.EVENTO_GESTIONAR_TODOS)):
        raise Forbidden()
    return evento


def para_escribir(repo: Eventos, usuario: User, id_evento: UUID) -> Event:
    """El evento bloqueado para modificarlo, si quien pregunta lo gestiona."""
    return _exigir_gestion(usuario, repo.por_id_para_escribir(id_evento))


def para_gestionar(repo: Eventos, usuario: User, id_evento: UUID) -> Event:
    """El evento para leer lo que solo ve quien lo gestiona, sin bloquearlo."""
    return _exigir_gestion(usuario, repo.por_id(id_evento))


def _cambiar_estado(
    repo: Eventos, evento: Event, desde: set[EstadoEvento], hacia: EstadoEvento
) -> Event:
    if evento.status not in desde:
        raise TransicionInvalida()
    evento.status = hacia
    return repo.guardar(evento)


def publicar(repo: Eventos, usuario: User, id_evento: UUID) -> ConInscritos:
    evento = para_escribir(repo, usuario, id_evento)
    if ya_empezo(evento):
        raise TransicionInvalida("No se publica un evento que ya empezó")
    evento = _cambiar_estado(repo, evento, {EstadoEvento.DRAFT}, EstadoEvento.PUBLISHED)
    return _con_inscritos(repo, evento)


def _con_inscripciones(detalle: str) -> Conflict:
    return Conflict(
        detalle, tipo="has-registrations", titulo="El evento tiene inscripciones activas"
    )


def despublicar(repo: Eventos, usuario: User, id_evento: UUID) -> ConInscritos:
    """Un evento con inscripciones activas no vuelve a borrador: dejaría de verlo quien se
    inscribió. El bloqueo de la fila hace que nadie se inscriba mientras tanto."""
    evento = para_escribir(repo, usuario, id_evento)
    if repo.inscritos([evento.id])[evento.id]:
        raise _con_inscripciones("Un evento con inscripciones activas no se despublica.")
    return ConInscritos(
        _cambiar_estado(repo, evento, {EstadoEvento.PUBLISHED}, EstadoEvento.DRAFT), 0
    )


def cancelar(repo: Eventos, usuario: User, id_evento: UUID) -> ConInscritos:
    evento = para_escribir(repo, usuario, id_evento)
    if finalizado(evento):
        raise TransicionInvalida("No se cancela un evento que ya terminó")
    desde = {EstadoEvento.DRAFT, EstadoEvento.PUBLISHED}
    # Las inscripciones no cambian: quedan activas y el estado del evento ya dice que se canceló.
    return _con_inscritos(repo, _cambiar_estado(repo, evento, desde, EstadoEvento.CANCELLED))


def _exigir_sesiones_adentro(repo: Eventos, evento: Event, inicio: datetime, fin: datetime) -> None:
    """Las fechas nuevas no pueden dejar sesiones afuera. El evento ya está bloqueado, así que
    nadie agrega una sesión mientras tanto."""
    afuera = sum(1 for s in repo.sesiones_de(evento.id) if s.start_at < inicio or s.end_at > fin)
    if afuera:
        detalle = (
            "1 sesión queda fuera de las fechas nuevas"
            if afuera == 1
            else f"{afuera} sesiones quedan fuera de las fechas nuevas"
        )
        raise Conflict(
            detalle,
            tipo="sessions-outside-range",
            titulo="Las fechas nuevas dejan sesiones fuera del evento",
        )


def _exigir_sesiones_que_entren(repo: Eventos, evento: Event, capacidad: int) -> None:
    """La capacidad nueva no puede quedar por debajo de la de una sesión. Las sesiones sin
    capacidad propia usan la del evento, así que no cuentan. El evento ya está bloqueado."""
    encima = sum(
        1 for s in repo.sesiones_de(evento.id) if s.capacity is not None and s.capacity > capacidad
    )
    if encima:
        detalle = (
            "1 sesión tiene más capacidad que la nueva"
            if encima == 1
            else f"{encima} sesiones tienen más capacidad que la nueva"
        )
        raise Conflict(
            detalle,
            tipo="sessions-capacity-above",
            titulo="La capacidad nueva deja sesiones por encima de la del evento",
        )


def _exigir_reservas_que_entren(repo: Eventos, evento: Event, capacidad: int) -> None:
    """Una sesión sin capacidad propia usa la del evento: la nueva no puede dejarla por debajo
    de sus reservas activas. El evento ya está bloqueado, así que nadie reserva mientras."""
    reservadas = repo.max_reservas_sin_capacidad(evento.id)
    if capacidad < reservadas:
        raise Conflict(
            f"Una sesión sin capacidad propia tiene {reservadas} reservas activas"
            f" y la capacidad nueva es {capacidad}.",
            tipo="capacity-below-reservations",
            titulo="La capacidad no puede quedar por debajo de las reservas",
        )


def editar(repo: Eventos, usuario: User, id_evento: UUID, datos: EventoEdicion) -> ConInscritos:
    """Las reglas de capacidad corren con el evento bloqueado. Primero las reservas de las
    sesiones: toda reserva activa cuelga de una inscripción activa, así que quedar por debajo
    de las reservas es también quedar por debajo de los inscritos, y si los inscritos fueran
    primero ese error no saldría nunca. Después los inscritos, que son personas con lugar
    tomado, y al final las sesiones, que se pueden achicar antes."""
    evento = para_escribir(repo, usuario, id_evento)
    if evento.status == EstadoEvento.CANCELLED or finalizado(evento):
        raise Conflict(titulo="Un evento cancelado o finalizado no se edita")
    cambios = datos.model_dump(exclude_unset=True)
    if "start_at" in cambios and cambios["start_at"] <= datetime.now(UTC):
        raise DatosInvalidos("start_at", "Tiene que estar en el futuro")
    if cambios.get("end_at", evento.end_at) <= cambios.get("start_at", evento.start_at):
        raise DatosInvalidos("end_at", "Tiene que ser posterior al inicio")
    if "start_at" in cambios or "end_at" in cambios:
        _exigir_sesiones_adentro(
            repo,
            evento,
            cambios.get("start_at", evento.start_at),
            cambios.get("end_at", evento.end_at),
        )
    activas = repo.inscritos([evento.id])[evento.id]
    if "capacity" in cambios:
        _exigir_reservas_que_entren(repo, evento, cambios["capacity"])
        if cambios["capacity"] < activas:
            raise Conflict(
                f"El evento ya tiene {activas} inscripciones activas.",
                tipo="capacity-below-registrations",
                titulo="La capacidad no puede quedar por debajo de los inscritos",
            )
        _exigir_sesiones_que_entren(repo, evento, cambios["capacity"])
    for campo, valor in cambios.items():
        setattr(evento, campo, valor)
    return ConInscritos(repo.guardar(evento), activas)


def eliminar(repo: Eventos, usuario: User, id_evento: UUID) -> None:
    """Con inscripciones activas no se borra: se perdería quién estaba inscrito. Cancelarlo sí
    las conserva."""
    evento = para_escribir(repo, usuario, id_evento)
    if repo.inscritos([evento.id])[evento.id]:
        raise _con_inscripciones("Cancelá el evento en lugar de eliminarlo")
    repo.eliminar(evento)
