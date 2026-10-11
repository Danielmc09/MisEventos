"""Datos de demostración: `python -m app.scripts.seed`.

Idempotente: crea lo que falta y no restaura lo que alguien cambió (contraseñas, emails).
El arranque del contenedor lo llama con --solo-si-seed-demo, después de las migraciones.
"""

import argparse
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from sqlmodel import Session

from app.core.config import Settings
from app.core.contrasenas import hashear
from app.core.db import crear_fabrica_de_sesiones, sesion_transaccional
from app.core.permisos import Rol
from app.models.usuario import User
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


def sembrar(session: Session, credenciales: CredencialesDemo) -> None:
    """Crea lo que falte de los datos de demostración, en la transacción recibida.

    Cada parte es idempotente. Los eventos demo se suman acá cuando existan.
    """
    sembrar_usuarios(RepositorioUsuarios(session), credenciales)


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
