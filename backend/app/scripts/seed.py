"""Datos de demostración: `python -m app.scripts.seed`.

Idempotente: crea lo que falta y no restaura lo que alguien cambió (contraseñas, emails).
El arranque del contenedor lo llama con --solo-si-seed-demo, después de las migraciones.
"""

import argparse
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
from app.core.permisos import Rol
from app.models.evento import EstadoEvento, Event
from app.models.usuario import User
from app.repositories.eventos import RepositorioEventos
from app.repositories.usuarios import RepositorioUsuarios
from app.services.autenticacion import Usuarios

ORGANIZADOR_DEMO = "organizador@miseventos.local"
ASISTENTE_DEMO = "asistente@miseventos.local"


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
# probar la búsqueda. Las inscripciones del casi lleno y las sesiones paralelas se agregan aparte.
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
        "Cupo reducido: quedan pocos lugares.",
        "Universidad Nacional, Bogotá",
        10,
        4,
        10,
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


def sembrar_eventos(usuarios: Usuarios, eventos: EventosDemo) -> None:
    """Crea los eventos demo que falten, a nombre del organizador demo. Uno que ya existe (mismo
    nombre y organizador) no se toca. Las fechas son relativas a hoy: la demo nunca queda vieja.
    Se crean por el repositorio, sin las reglas del servicio: uno de ellos ya terminó."""
    organizador = usuarios.por_email(ORGANIZADOR_DEMO)
    if organizador is None:
        raise RuntimeError(f"Falta el usuario {ORGANIZADOR_DEMO}, dueño de los eventos demo")
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


def sembrar(session: Session, credenciales: CredencialesDemo) -> None:
    """Crea lo que falte de los datos de demostración, en la transacción recibida.

    Cada parte es idempotente. Primero los usuarios: el organizador demo es dueño de los eventos.
    """
    usuarios = RepositorioUsuarios(session)
    sembrar_usuarios(usuarios, credenciales)
    sembrar_eventos(usuarios, RepositorioEventos(session))


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
