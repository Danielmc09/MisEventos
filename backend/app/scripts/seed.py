"""Datos de demostración: `python -m app.scripts.seed`.

Idempotente: crea lo que falta y no restaura lo que alguien cambió (contraseñas, emails).
El arranque del contenedor lo llama con --solo-si-seed-demo, después de las migraciones.
"""

import argparse
import logging
import secrets
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlmodel import Session

from app.core.config import Settings
from app.core.contrasenas import hashear
from app.core.db import crear_fabrica_de_sesiones, sesion_transaccional
from app.core.excepciones import Conflict, DatosInvalidos, DomainError, NotFound
from app.core.permisos import Rol
from app.models.evento import EstadoEvento, Event
from app.models.inscripcion import EstadoInscripcion, Registration
from app.models.ponente import Speaker
from app.models.reserva import SessionRegistration
from app.models.usuario import User
from app.repositories.eventos import RepositorioEventos
from app.repositories.inscripciones import RepositorioInscripciones
from app.repositories.ponentes import RepositorioPonentes
from app.repositories.reservas import RepositorioReservas
from app.repositories.sesiones import RepositorioSesiones
from app.repositories.usuarios import RepositorioUsuarios
from app.schemas.sesiones import SesionEntrada
from app.services import reservas as servicio_reservas
from app.services import sesiones as servicio_sesiones
from app.services.autenticacion import Usuarios
from app.services.eventos import Eventos
from app.services.ponentes import Ponentes
from app.services.reservas import InscripcionesParaReservar, Reservas
from app.services.sesiones import Sesiones

ORGANIZADOR_DEMO = "organizador@miseventos.local"
ASISTENTE_DEMO = "asistente@miseventos.local"

logger = logging.getLogger("miseventos.seed")


@dataclass(frozen=True)
class CredencialesDemo:
    admin_email: str
    admin_password: str
    demo_password: str


def credenciales_demo(settings: Settings) -> CredencialesDemo:
    valores = {
        "ADMIN_EMAIL": settings.admin_email,
        "ADMIN_PASSWORD": settings.admin_password,
        "DEMO_PASSWORD": settings.demo_password,
    }
    faltan = [nombre for nombre, valor in valores.items() if not valor]
    if faltan:
        raise RuntimeError("El seed necesita estas variables de entorno: " + ", ".join(faltan))
    return CredencialesDemo(
        admin_email=valores["ADMIN_EMAIL"],
        admin_password=valores["ADMIN_PASSWORD"],
        demo_password=valores["DEMO_PASSWORD"],
    )


def sembrar_usuarios(repo: Usuarios, credenciales: CredencialesDemo) -> None:
    """Crea el admin y los usuarios demo que falten. Al que ya existe solo le completa el
    nombre si no tiene; su contraseña, email, rol y un nombre propio no se tocan.
    Entran directo, sin cambio obligatorio de contraseña."""
    demo = [
        (credenciales.admin_email, credenciales.admin_password, Rol.ADMIN, "Ana Administradora"),
        (ORGANIZADOR_DEMO, credenciales.demo_password, Rol.ORGANIZER, "Oscar Organizador"),
        (ASISTENTE_DEMO, credenciales.demo_password, Rol.ATTENDEE, "Andrea Asistente"),
    ]
    for email, password, rol, nombre in demo:
        existente = repo.por_email(email)
        if existente is None:
            repo.crear(
                User(
                    email=email,
                    password_hash=hashear(password),
                    role=rol,
                    full_name=nombre,
                    is_active=True,
                    must_change_password=False,
                )
            )
        elif not existente.full_name:
            existente.full_name = nombre  # la transacción del seed lo guarda al confirmar


class EventosDemo(Protocol):
    def por_nombre_y_organizador(self, nombre: str, organizer_id: UUID) -> Event | None: ...
    def crear(self, evento: Event) -> Event: ...


@dataclass(frozen=True)
class EventoDemo:
    nombre: str
    descripcion: str
    lugar: str
    empieza_en_dias: int
    horas: int
    capacidad: int
    estado: EstadoEvento


# Uno de cada caso que la demo necesita mostrar. Dos dicen "Python" con distintas mayúsculas, para
# probar la búsqueda. Las inscripciones del casi lleno se agregan aparte; las sesiones, abajo.
EVENTOS_DEMO = [
    EventoDemo(
        "PyCon Bogotá",
        "La conferencia de la comunidad Python en Colombia.",
        "Ágora Bogotá",
        30,
        9,
        300,
        EstadoEvento.PUBLISHED,
    ),
    EventoDemo(
        "Taller de python para principiantes",
        "Taller práctico para quienes empiezan con Python.",
        "Universidad Nacional, Bogotá",
        10,
        4,
        3,
        EstadoEvento.PUBLISHED,
    ),
    EventoDemo(
        "Meetup de ciencia de datos",
        "Todavía en preparación.",
        "Medellín",
        45,
        3,
        80,
        EstadoEvento.DRAFT,
    ),
    EventoDemo(
        "Jornada de seguridad web",
        "Se canceló por fuerza mayor.",
        "Cali",
        20,
        6,
        120,
        EstadoEvento.CANCELLED,
    ),
    EventoDemo(
        "Encuentro DevOps Colombia",
        "Ya se realizó.",
        "Barranquilla",
        -30,
        8,
        150,
        EstadoEvento.PUBLISHED,
    ),
    EventoDemo(
        "Python Day Medellín",
        "Charlas en salas paralelas durante todo el día.",
        "Plaza Mayor, Medellín",
        21,
        9,
        250,
        EstadoEvento.PUBLISHED,
    ),
]


def _organizador(usuarios: Usuarios) -> User:
    organizador = usuarios.por_email(ORGANIZADOR_DEMO)
    if organizador is None:
        raise RuntimeError(f"Falta el usuario {ORGANIZADOR_DEMO}, dueño de los eventos demo")
    return organizador


def sembrar_eventos(usuarios: Usuarios, eventos: EventosDemo) -> None:
    """Crea los eventos demo que falten, a nombre del organizador demo. Uno que ya existe (mismo
    nombre y organizador) no se toca. Las fechas son relativas a hoy: la demo nunca queda vieja.
    Se crean por el repositorio, sin las reglas del servicio: uno de ellos ya terminó."""
    organizador = _organizador(usuarios)
    # 14:00 UTC son las 9:00 en Bogotá.
    hoy = datetime.now(UTC).replace(hour=14, minute=0, second=0, microsecond=0)
    for demo in EVENTOS_DEMO:
        if eventos.por_nombre_y_organizador(demo.nombre, organizador.id) is not None:
            continue
        inicio = hoy + timedelta(days=demo.empieza_en_dias)
        eventos.crear(
            Event(
                name=demo.nombre,
                description=demo.descripcion,
                location=demo.lugar,
                start_at=inicio,
                end_at=inicio + timedelta(hours=demo.horas),
                capacity=demo.capacidad,
                status=demo.estado,
                organizer_id=organizador.id,
            )
        )


class PonentesDemo(Ponentes, Protocol):
    def por_email_y_creador(self, email: str, creador: UUID) -> Speaker | None: ...


class EventosConSesiones(Eventos, EventosDemo, Protocol): ...


@dataclass(frozen=True)
class PonenteDemo:
    nombre: str
    email: str
    bio: str


@dataclass(frozen=True)
class SesionDemo:
    evento: str
    titulo: str
    descripcion: str
    sala: str
    desde_el_inicio: timedelta
    duracion: timedelta
    capacidad: int | None
    ponentes: tuple[str, ...]  # emails de PONENTES_DEMO


ANA = "ana.perez@ponentes.example"
CARLOS = "carlos.gomez@ponentes.example"
LAURA = "laura.restrepo@ponentes.example"
DIEGO = "diego.martinez@ponentes.example"

PONENTES_DEMO = [
    PonenteDemo("Ana Pérez", ANA, "Desarrolladora backend; mantiene plugins de pytest."),
    PonenteDemo("Carlos Gómez", CARLOS, "Científico de datos en el sector salud."),
    PonenteDemo("Laura Restrepo", LAURA, "Ingeniera de seguridad de aplicaciones web."),
    PonenteDemo("Diego Martínez", DIEGO, "Docente de programación y autor de cursos de APIs."),
]

PYTHON_DAY = "Python Day Medellín"
TALLER_DE_APIS = "Tu primera API con FastAPI"

# Python Day Medellín: dos sesiones paralelas en salas distintas, una con dos ponentes y un taller
# chico, que las reservas demo dejan con un solo lugar.
# Ana Pérez también habla en PyCon Bogotá, otro día: un ponente en dos eventos, sin cruces.
SESIONES_DEMO = [
    SesionDemo(
        "Python Day Medellín",
        "Testing en Python",
        "Cómo escribir tests que fallan por la razón correcta.",
        "Sala A",
        timedelta(hours=1),
        timedelta(hours=1),
        120,
        (ANA,),
    ),
    SesionDemo(
        "Python Day Medellín",
        "Pandas para análisis de datos",
        "De un CSV desordenado a un reporte, paso a paso.",
        "Sala B",
        timedelta(hours=1),
        timedelta(hours=1),
        100,
        (CARLOS,),
    ),
    SesionDemo(
        "Python Day Medellín",
        "Seguridad en APIs con FastAPI",
        "Autenticación, permisos e inyección: los errores más comunes y cómo evitarlos.",
        "Sala A",
        timedelta(hours=3),
        timedelta(minutes=90),
        None,
        (LAURA, DIEGO),
    ),
    SesionDemo(
        "Python Day Medellín",
        TALLER_DE_APIS,
        "Taller práctico en grupo chico: se programa en parejas desde el primer minuto.",
        "Sala C",
        timedelta(hours=5),
        timedelta(hours=1),
        3,
        (DIEGO,),
    ),
    SesionDemo(
        "PyCon Bogotá",
        "Testing en Python: de cero a integración continua",
        "Una suite que corre en cada cambio, desde el primer test.",
        "Auditorio principal",
        timedelta(hours=2),
        timedelta(hours=1),
        None,
        (ANA,),
    ),
]


def sembrar_ponentes(usuarios: Usuarios, ponentes: PonentesDemo) -> None:
    """Crea los ponentes demo que falten, a nombre del organizador demo. Uno que ya existe (mismo
    email y creador) no se toca, aunque le hayan cambiado la bio o el nombre."""
    organizador = _organizador(usuarios)
    for demo in PONENTES_DEMO:
        if ponentes.por_email_y_creador(demo.email, organizador.id) is not None:
            continue
        ponentes.crear(
            Speaker(
                full_name=demo.nombre,
                email=demo.email,
                bio=demo.bio,
                created_by=organizador.id,
            )
        )


def sembrar_sesiones(
    usuarios: Usuarios,
    eventos: EventosConSesiones,
    sesiones: Sesiones,
    ponentes: PonentesDemo,
) -> None:
    """Crea las sesiones demo que falten (mismo título en el mismo evento demo = ya existe, y no
    se toca). Se crean por el servicio, como el organizador demo: valen las mismas reglas de
    horario y los mismos bloqueos que en la API. Las horas son relativas al inicio del evento.
    Una sesión que ya no entra (alguien cambió el evento o la agenda) se saltea: la demo no
    frena el arranque."""
    organizador = _organizador(usuarios)
    for demo in SESIONES_DEMO:
        evento = eventos.por_nombre_y_organizador(demo.evento, organizador.id)
        if evento is None:
            continue
        if any(s.title == demo.titulo for s in eventos.sesiones_de(evento.id)):
            continue
        ids_ponente = []
        for email in demo.ponentes:
            ponente = ponentes.por_email_y_creador(email, organizador.id)
            if ponente is not None:
                ids_ponente.append(ponente.id)
        inicio = evento.start_at + demo.desde_el_inicio
        datos = SesionEntrada(
            title=demo.titulo,
            description=demo.descripcion,
            room=demo.sala,
            start_at=inicio,
            end_at=inicio + demo.duracion,
            capacity=demo.capacidad,
            speaker_ids=ids_ponente,
        )
        try:
            servicio_sesiones.crear(eventos, sesiones, ponentes, organizador, evento.id, datos)
        except (Conflict, DatosInvalidos) as error:
            logger.warning(
                "seed: no se creó la sesión «%s» del evento «%s»: %s",
                demo.titulo,
                demo.evento,
                _motivo(error),
            )


class InscripcionesDemo(Protocol):
    def alguna_de(self, id_usuario: UUID, id_evento: UUID) -> Registration | None: ...
    def crear(self, inscripcion: Registration) -> Registration: ...


CASI_LLENO = "Taller de python para principiantes"

# Las del asistente demo, para que su perfil muestre las tres pestañas. No está en el casi lleno:
# así puede tomar el último cupo en la demo.
INSCRIPCIONES_DEL_ASISTENTE = [
    ("PyCon Bogotá", EstadoInscripcion.ACTIVE),
    ("Python Day Medellín", EstadoInscripcion.ACTIVE),
    ("Jornada de seguridad web", EstadoInscripcion.CANCELLED),
]

# Asistentes que solo existen para ocupar lugares: dos en el casi lleno, sobre una capacidad de
# tres, y dos en el taller de Python Day, también de tres (para eso se inscriben a ese evento).
INSCRITOS_DEMO = [
    ("Camila Torres", "camila.torres@asistentes.example"),
    ("Julián Herrera", "julian.herrera@asistentes.example"),
]


def _inscritos_demo(usuarios: Usuarios) -> list[User]:
    """Crea los que falten. Nadie entra con ellos: la contraseña es aleatoria y no se guarda."""
    inscritos = []
    for nombre, email in INSCRITOS_DEMO:
        usuario = usuarios.por_email(email)
        if usuario is None:
            usuario = User(
                email=email,
                password_hash=hashear(secrets.token_urlsafe(32)),
                role=Rol.ATTENDEE,
                full_name=nombre,
                is_active=True,
                must_change_password=False,
            )
            usuarios.crear(usuario)
        inscritos.append(usuario)
    return inscritos


def sembrar_inscripciones(
    usuarios: Usuarios, eventos: EventosConSesiones, inscripciones: InscripcionesDemo
) -> None:
    """Crea las inscripciones demo que falten. Si la persona ya tiene una en ese evento, activa o
    cancelada, no se toca: no se reactiva lo que alguien canceló. Nunca se pasa del cupo, aunque
    alguien haya achicado el evento. Van por el repositorio: una es de un evento cancelado."""
    organizador = _organizador(usuarios)
    asistente = usuarios.por_email(ASISTENTE_DEMO)
    if asistente is None:
        raise RuntimeError(f"Falta el usuario {ASISTENTE_DEMO}, el asistente de la demo")
    pendientes = [(asistente, evento, estado) for evento, estado in INSCRIPCIONES_DEL_ASISTENTE]
    for relleno in _inscritos_demo(usuarios):
        pendientes += [
            (relleno, CASI_LLENO, EstadoInscripcion.ACTIVE),
            (relleno, PYTHON_DAY, EstadoInscripcion.ACTIVE),
        ]
    for usuario, nombre_evento, estado in pendientes:
        evento = eventos.por_nombre_y_organizador(nombre_evento, organizador.id)
        if evento is None or inscripciones.alguna_de(usuario.id, evento.id) is not None:
            continue
        activa = estado == EstadoInscripcion.ACTIVE
        if activa and eventos.inscritos([evento.id])[evento.id] >= evento.capacity:
            continue
        inscripciones.crear(
            Registration(
                user_id=usuario.id,
                event_id=evento.id,
                status=estado,
                cancelled_at=None if activa else datetime.now(UTC),
            )
        )


class ReservasDemo(Reservas, Protocol):
    def alguna_de(self, id_usuario: UUID, id_sesion: UUID) -> SessionRegistration | None: ...


# Las del asistente demo, en Python Day: dos sesiones que no se cruzan. La paralela a la primera
# ("Pandas para análisis de datos") queda libre para mostrar el bloqueo por cruce, y el taller,
# con su último lugar, para que lo tome.
RESERVAS_DEL_ASISTENTE = ["Testing en Python", "Seguridad en APIs con FastAPI"]


def sembrar_reservas(
    usuarios: Usuarios,
    eventos: EventosConSesiones,
    sesiones: Sesiones,
    inscripciones: InscripcionesParaReservar,
    reservas: ReservasDemo,
) -> None:
    """Crea las reservas demo que falten en Python Day: las dos del asistente demo y las de los
    inscritos de relleno en el taller, que lo dejan con un solo lugar. Si la persona ya tiene una
    reserva en esa sesión, activa o cancelada, no se toca: no se reactiva lo que alguien canceló.
    Van por el servicio, con sus reglas y sus bloqueos; una que no entra (sin inscripción, sin
    lugar, con un cruce) se saltea con un aviso y la demo sigue."""
    organizador = _organizador(usuarios)
    evento = eventos.por_nombre_y_organizador(PYTHON_DAY, organizador.id)
    if evento is None:
        return
    asistente = usuarios.por_email(ASISTENTE_DEMO)
    if asistente is None:
        raise RuntimeError(f"Falta el usuario {ASISTENTE_DEMO}, el asistente de la demo")
    pendientes = [(asistente, titulo) for titulo in RESERVAS_DEL_ASISTENTE]
    pendientes += [(relleno, TALLER_DE_APIS) for relleno in _inscritos_demo(usuarios)]
    por_titulo = {s.title: s for s in eventos.sesiones_de(evento.id)}
    for usuario, titulo in pendientes:
        sesion = por_titulo.get(titulo)
        if sesion is None or reservas.alguna_de(usuario.id, sesion.id) is not None:
            continue
        try:
            servicio_reservas.reservar(
                eventos, sesiones, inscripciones, reservas, usuario, sesion.id
            )
        except (Conflict, NotFound) as error:
            logger.warning(
                "seed: no se creó una reserva en la sesión «%s» del evento «%s»: %s",
                titulo,
                PYTHON_DAY,
                _motivo(error),
            )


def _motivo(error: DomainError) -> str:
    """El porqué legible: el detalle, o el mensaje de cada campo si fue un dato rechazado."""
    if error.errores:
        return "; ".join(f"{campo}: {mensaje}" for campo, mensaje in error.errores.items())
    return str(error)


def sembrar(session: Session, credenciales: CredencialesDemo) -> None:
    """Crea lo que falte de los datos de demostración, en la transacción recibida.

    Cada parte es idempotente. El orden importa: el organizador demo es dueño de los eventos y
    de los ponentes, las sesiones cuelgan de los dos, las inscripciones de los eventos y las
    reservas, de las sesiones y de las inscripciones.
    """
    usuarios = RepositorioUsuarios(session)
    eventos = RepositorioEventos(session)
    ponentes = RepositorioPonentes(session)
    sesiones = RepositorioSesiones(session)
    inscripciones = RepositorioInscripciones(session)
    sembrar_usuarios(usuarios, credenciales)
    sembrar_eventos(usuarios, eventos)
    sembrar_ponentes(usuarios, ponentes)
    sembrar_sesiones(usuarios, eventos, sesiones, ponentes)
    sembrar_inscripciones(usuarios, eventos, inscripciones)
    sembrar_reservas(usuarios, eventos, sesiones, inscripciones, RepositorioReservas(session))


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Carga los datos de demostración.")
    parser.add_argument(
        "--solo-si-seed-demo",
        action="store_true",
        help="no hace nada si SEED_DEMO no es true (lo usa el arranque)",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    if args.solo_si_seed_demo and not settings.seed_demo:
        return
    try:
        credenciales = credenciales_demo(settings)
    except RuntimeError as error:
        raise SystemExit(f"seed: {error}") from error

    fabrica = crear_fabrica_de_sesiones(settings.database_url)
    with contextmanager(sesion_transaccional)(fabrica) as session:
        sembrar(session, credenciales)


if __name__ == "__main__":
    main()
