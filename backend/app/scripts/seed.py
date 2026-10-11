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
from app.core.db import crear_fabrica_de_sesiones, sesion_transaccional


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


def sembrar_usuarios(repo, credenciales: CredencialesDemo) -> None:
    pass


def sembrar(session: Session, credenciales: CredencialesDemo) -> None:
    """Crea lo que falte de los datos de demostración, en la transacción recibida.

    Todavía no hay tablas de dominio. Acá se suman, cada uno idempotente:
    el admin y los usuarios demo (organizador y asistente, sin cambio obligatorio de
    contraseña) y los eventos demo con fechas relativas al momento del seed.
    """


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
